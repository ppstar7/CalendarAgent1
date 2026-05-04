from __future__ import annotations

import argparse
import calendar
import json
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from analyst_agent.google_calendar_weekly import (
    DEFAULT_TIMEZONE,
    fetch_events,
    floor_to_week,
    list_calendars,
    load_credentials,
)


DEFAULT_GOAL = "Land a job in Customer Success"
HIGH_SIGNAL_KEYWORDS = {
    "customer success": 6,
    "customer success manager": 7,
    "client success": 6,
    "csm": 4,
    "customer onboarding": 6,
    "onboarding": 3,
    "implementation": 3,
    "retention": 4,
    "renewal": 4,
    "renewals": 4,
    "expansion": 3,
    "account management": 4,
    "account manager": 4,
    "customer support": 3,
    "support": 1,
    "saas": 3,
    "crm": 3,
    "gainsight": 4,
    "zendesk": 3,
    "hubspot": 3,
    "salesforce": 3,
    "interview": 7,
    "recruiter": 6,
    "hiring": 6,
    "job fair": 5,
    "career fair": 5,
    "networking": 5,
    "coffee chat": 5,
    "mentor": 3,
    "mentorship": 3,
    "webinar": 2,
    "workshop": 2,
    "training": 2,
    "alumni": 3,
    "customer": 2,
    "client": 2,
}
LOW_SIGNAL_KEYWORDS = {
    "birthday": -6,
    "party": -5,
    "brunch": -4,
    "lunch": -3,
    "dinner": -3,
    "gym": -5,
    "workout": -5,
    "yoga": -5,
    "dentist": -6,
    "doctor": -6,
    "haircut": -6,
    "vacation": -7,
    "holiday": -4,
    "school pickup": -6,
    "pickup": -4,
    "grocery": -6,
    "errand": -5,
}
TARGET_COMPANIES = {
    "salesforce",
    "zendesk",
    "hubspot",
    "slack",
    "atlassian",
    "gainsight",
    "intercom",
    "microsoft",
    "google",
    "amazon",
    "notion",
    "stripe",
    "asana",
    "monday",
    "servicenow",
}


@dataclass
class ReviewedEvent:
    start: str
    end: str | None
    title: str
    location: str
    score: int
    verdict: str
    action: str
    reasons: list[str]
    organizer: str
    attendees: int
    week_start: str
    helpful: bool


@dataclass
class ReportWindow:
    report_start: date
    report_end: date
    week_summary_start: date
    week_count: int


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Review Google Calendar events for relevance to a Customer Success job search."
    )
    parser.add_argument("--credentials", default="credentials.json")
    parser.add_argument("--token", default="token.json")
    parser.add_argument("--calendar-id", default="primary")
    parser.add_argument("--weeks", type=int, default=8, help="Number of upcoming weeks to review.")
    parser.add_argument(
        "--month",
        help="Optional month to review in YYYY-MM format, for example 2026-05.",
    )
    parser.add_argument("--timezone", default=DEFAULT_TIMEZONE)
    parser.add_argument("--week-start", choices=["monday", "sunday"], default="monday")
    parser.add_argument("--goal", default=DEFAULT_GOAL, help="Career goal used in the report header.")
    parser.add_argument(
        "--include-cancelled",
        action="store_true",
        help="Include cancelled events in the review.",
    )
    parser.add_argument(
        "--list-calendars",
        action="store_true",
        help="List available Google calendars and exit.",
    )
    parser.add_argument(
        "--json",
        help="Optional path to write the full report as JSON.",
    )
    parser.add_argument(
        "--pdf",
        help="Optional path to write the report as PDF.",
    )
    return parser


def resolve_report_window(args: argparse.Namespace, zone: ZoneInfo) -> ReportWindow:
    if args.month:
        try:
            year_text, month_text = args.month.split("-", maxsplit=1)
            year = int(year_text)
            month = int(month_text)
            first_day = date(year, month, 1)
        except ValueError as exc:
            raise SystemExit("--month must use YYYY-MM format, for example 2026-05.") from exc

        last_day = date(year, month, calendar.monthrange(year, month)[1])
        first_week_start = floor_to_week(first_day, args.week_start)
        last_week_start = floor_to_week(last_day, args.week_start)
        week_count = ((last_week_start - first_week_start).days // 7) + 1
        return ReportWindow(
            report_start=first_day,
            report_end=last_day,
            week_summary_start=first_week_start,
            week_count=week_count,
        )

    today = datetime.now(zone).date()
    first_week_start = floor_to_week(today, args.week_start)
    final_day = first_week_start + timedelta(days=(args.weeks * 7) - 1)
    return ReportWindow(
        report_start=today,
        report_end=final_day,
        week_summary_start=first_week_start,
        week_count=args.weeks,
    )


def event_timestamp(event: dict[str, Any], key: str, zone: ZoneInfo) -> datetime:
    payload = event.get(key, {})
    if "dateTime" in payload:
        return datetime.fromisoformat(payload["dateTime"].replace("Z", "+00:00")).astimezone(zone)
    if "date" in payload:
        return datetime.combine(date.fromisoformat(payload["date"]), time.min, tzinfo=zone)
    raise ValueError(f"Event missing {key}: {event.get('id', '<unknown>')}")


def describe_location(event: dict[str, Any]) -> str:
    if event.get("location"):
        return str(event["location"])
    conference = event.get("conferenceData", {}).get("entryPoints", [])
    for entry in conference:
        uri = entry.get("uri")
        if uri:
            return f"Virtual ({uri})"
    if event.get("hangoutLink"):
        return f"Virtual ({event['hangoutLink']})"
    return "Not specified"


def review_event(event: dict[str, Any], zone: ZoneInfo, week_start: str) -> ReviewedEvent:
    title = str(event.get("summary") or "(Untitled event)")
    description = str(event.get("description") or "")
    location = describe_location(event)
    organizer = str(event.get("organizer", {}).get("email") or "")
    attendees = len(event.get("attendees", []))
    combined = " ".join([title, description, location, organizer]).lower()

    score = 0
    reasons: list[str] = []

    for keyword, weight in HIGH_SIGNAL_KEYWORDS.items():
        if keyword in combined:
            score += weight
            reasons.append(f"Matches '{keyword}'")

    for keyword, weight in LOW_SIGNAL_KEYWORDS.items():
        if keyword in combined:
            score += weight
            reasons.append(f"Looks personal or low-signal because of '{keyword}'")

    if "interview" in combined or "recruiter" in combined:
        reasons.append("Directly tied to hiring conversations")
    if any(company in combined for company in TARGET_COMPANIES):
        score += 3
        reasons.append("Touches a target SaaS company or tool often used in Customer Success")
    if attendees >= 4:
        score += 1
        reasons.append("Includes multiple attendees, which may create networking or context value")
    if "virtual" in location.lower():
        score += 1
        reasons.append("Easy to attend remotely")
    if location == "Not specified":
        reasons.append("Location is missing, so the value is harder to judge")

    start_at = event_timestamp(event, "start", zone)
    try:
        end_at = event_timestamp(event, "end", zone)
    except ValueError:
        end_at = None

    if score >= 8:
        verdict = "High value"
        action = "Keep and prepare"
        helpful = True
    elif score >= 3:
        verdict = "Maybe useful"
        action = "Review manually"
        helpful = True
    else:
        verdict = "Low value"
        action = "Consider declining or deprioritizing"
        helpful = False

    week = floor_to_week(start_at.date(), week_start).isoformat()
    if not reasons:
        reasons.append("No strong Customer Success or job-search signal found in the event details")

    return ReviewedEvent(
        start=start_at.isoformat(),
        end=end_at.isoformat() if end_at else None,
        title=title,
        location=location,
        score=score,
        verdict=verdict,
        action=action,
        reasons=reasons[:4],
        organizer=organizer or "Unknown",
        attendees=attendees,
        week_start=week,
        helpful=helpful,
    )


def weekly_counts(reviews: list[ReviewedEvent], start_day: date, weeks: int) -> list[dict[str, Any]]:
    total_counts: Counter[str] = Counter()
    helpful_counts: Counter[str] = Counter()
    high_value_counts: Counter[str] = Counter()

    for review in reviews:
        total_counts[review.week_start] += 1
        if review.helpful:
            helpful_counts[review.week_start] += 1
        if review.verdict == "High value":
            high_value_counts[review.week_start] += 1

    rows = []
    current = start_day
    for _ in range(weeks):
        week_key = current.isoformat()
        rows.append(
            {
                "week_start": week_key,
                "week_end": (current + timedelta(days=6)).isoformat(),
                "event_count": total_counts.get(week_key, 0),
                "helpful_event_count": helpful_counts.get(week_key, 0),
                "high_value_event_count": high_value_counts.get(week_key, 0),
            }
        )
        current += timedelta(days=7)
    return rows


def build_report(
    calendar_id: str,
    goal: str,
    timezone_name: str,
    report_start: date,
    report_end: date,
    reviews: list[ReviewedEvent],
    weekly_summary: list[dict[str, Any]],
) -> dict[str, Any]:
    verdict_counts = Counter(review.verdict for review in reviews)
    top_locations = Counter(review.location for review in reviews if review.location != "Not specified").most_common(5)

    return {
        "goal": goal,
        "calendar_id": calendar_id,
        "timezone": timezone_name,
        "report_start": report_start.isoformat(),
        "report_end": report_end.isoformat(),
        "summary": {
            "total_upcoming_events": len(reviews),
            "high_value_events": verdict_counts.get("High value", 0),
            "maybe_useful_events": verdict_counts.get("Maybe useful", 0),
            "low_value_events": verdict_counts.get("Low value", 0),
            "helpful_share": round(
                ((verdict_counts.get("High value", 0) + verdict_counts.get("Maybe useful", 0)) / len(reviews)) * 100,
                1,
            )
            if reviews
            else 0.0,
        },
        "weekly_summary": weekly_summary,
        "top_locations": [{"location": location, "count": count} for location, count in top_locations],
        "events": [asdict(review) for review in reviews],
    }


def print_report(report: dict[str, Any]) -> None:
    summary = report["summary"]
    print(f"Goal: {report['goal']}")
    print(f"Calendar: {report['calendar_id']}")
    print(f"Timezone: {report['timezone']}")
    print(f"Date range: {report['report_start']} to {report['report_end']}")
    print(f"Events reviewed: {summary['total_upcoming_events']}")
    print(
        "Helpful signal: "
        f"{summary['high_value_events']} high value, "
        f"{summary['maybe_useful_events']} maybe useful, "
        f"{summary['low_value_events']} low value"
    )
    print(f"Helpful share: {summary['helpful_share']}%")
    print("")
    print("Weekly view")
    print("week_start,week_end,event_count,helpful_event_count,high_value_event_count")
    for row in report["weekly_summary"]:
        print(
            f"{row['week_start']},{row['week_end']},{row['event_count']},"
            f"{row['helpful_event_count']},{row['high_value_event_count']}"
        )

    print("")
    print("Event review")
    for event in report["events"]:
        print(
            f"- {event['start']} | {event['title']} | {event['location']} | "
            f"{event['verdict']} | action: {event['action']}"
        )
        print(f"  reasons: {', '.join(event['reasons'])}")


def write_pdf_report(report: dict[str, Any], output_path: Path) -> None:
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError as exc:
        raise SystemExit("PDF export requires reportlab. Install it with: pip3 install reportlab") from exc

    summary = report["summary"]
    styles = getSampleStyleSheet()
    title_style = styles["Title"]
    heading_style = styles["Heading2"]
    body_style = styles["BodyText"]
    body_style.spaceAfter = 6
    small_style = ParagraphStyle(
        "SmallBody",
        parent=styles["BodyText"],
        fontSize=9,
        leading=12,
        spaceAfter=4,
    )

    story: list[Any] = []
    story.append(Paragraph("Customer Success Calendar Review", title_style))
    story.append(Spacer(1, 0.15 * inch))
    story.append(Paragraph(f"Goal: {report['goal']}", body_style))
    story.append(Paragraph(f"Calendar: {report['calendar_id']}", body_style))
    story.append(Paragraph(f"Timezone: {report['timezone']}", body_style))
    story.append(Paragraph(f"Date range: {report['report_start']} to {report['report_end']}", body_style))
    story.append(Spacer(1, 0.15 * inch))

    story.append(Paragraph("Summary", heading_style))
    summary_rows = [
        ["Metric", "Value"],
        ["Events reviewed", str(summary["total_upcoming_events"])],
        ["High value", str(summary["high_value_events"])],
        ["Maybe useful", str(summary["maybe_useful_events"])],
        ["Low value", str(summary["low_value_events"])],
        ["Helpful share", f"{summary['helpful_share']}%"],
    ]
    summary_table = Table(summary_rows, colWidths=[2.5 * inch, 2.0 * inch])
    summary_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#17324d")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.HexColor("#edf4fb")]),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(summary_table)
    story.append(Spacer(1, 0.2 * inch))

    story.append(Paragraph("Weekly View", heading_style))
    weekly_rows = [["Week start", "Week end", "All events", "Helpful", "High value"]]
    for row in report["weekly_summary"]:
        weekly_rows.append(
            [
                row["week_start"],
                row["week_end"],
                str(row["event_count"]),
                str(row["helpful_event_count"]),
                str(row["high_value_event_count"]),
            ]
        )
    weekly_table = Table(
        weekly_rows,
        colWidths=[1.25 * inch, 1.25 * inch, 1.0 * inch, 1.0 * inch, 1.0 * inch],
        repeatRows=1,
    )
    weekly_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4c7a34")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.HexColor("#f4f8ef")]),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("PADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(weekly_table)
    story.append(Spacer(1, 0.2 * inch))

    if report["top_locations"]:
        story.append(Paragraph("Top Locations", heading_style))
        for item in report["top_locations"]:
            story.append(Paragraph(f"{item['location']} ({item['count']} events)", body_style))
        story.append(Spacer(1, 0.15 * inch))

    story.append(PageBreak())
    story.append(Paragraph("Event Review", heading_style))
    for event in report["events"]:
        story.append(
            Paragraph(
                f"<b>{event['title']}</b><br/>"
                f"{event['start']}<br/>"
                f"Location: {event['location']}<br/>"
                f"Verdict: {event['verdict']}<br/>"
                f"Action: {event['action']}",
                body_style,
            )
        )
        story.append(Paragraph(f"Reasons: {', '.join(event['reasons'])}", small_style))
        story.append(Paragraph(f"Organizer: {event['organizer']} | Attendees: {event['attendees']}", small_style))
        story.append(Spacer(1, 0.12 * inch))

    document = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        leftMargin=0.65 * inch,
        rightMargin=0.65 * inch,
        topMargin=0.7 * inch,
        bottomMargin=0.7 * inch,
    )
    document.build(story)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    zone = ZoneInfo(args.timezone)
    report_window = resolve_report_window(args, zone)
    window_start = datetime.combine(report_window.report_start, time.min, tzinfo=zone)
    window_end = datetime.combine(report_window.report_end + timedelta(days=1), time.min, tzinfo=zone)

    credentials_path = Path(args.credentials).expanduser().resolve()
    token_path = Path(args.token).expanduser().resolve()
    creds = load_credentials(credentials_path, token_path)

    try:
        service = build("calendar", "v3", credentials=creds)
        if args.list_calendars:
            print(json.dumps(list_calendars(service), indent=2))
            return

        events = fetch_events(
            service=service,
            calendar_id=args.calendar_id,
            start_at=window_start,
            end_at=window_end,
            include_cancelled=args.include_cancelled,
        )
    except HttpError as exc:
        raise SystemExit(f"Google Calendar API error: {exc}") from exc

    if not args.include_cancelled:
        events = [event for event in events if event.get("status") != "cancelled"]

    reviews = [review_event(event=event, zone=zone, week_start=args.week_start) for event in events]
    reviews.sort(key=lambda item: item.start)

    report = build_report(
        calendar_id=args.calendar_id,
        goal=args.goal,
        timezone_name=args.timezone,
        report_start=report_window.report_start,
        report_end=report_window.report_end,
        reviews=reviews,
        weekly_summary=weekly_counts(reviews, report_window.week_summary_start, report_window.week_count),
    )

    if args.json:
        Path(args.json).expanduser().resolve().write_text(json.dumps(report, indent=2), encoding="utf-8")
    if args.pdf:
        write_pdf_report(report, Path(args.pdf).expanduser().resolve())

    print_report(report)


if __name__ == "__main__":
    main()
