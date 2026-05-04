from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
DEFAULT_TIMEZONE = "America/Los_Angeles"


@dataclass
class WeeklyCount:
    week_start: date
    week_end: date
    count: int


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Connect to Google Calendar and count how many events occur per week."
    )
    parser.add_argument(
        "--credentials",
        default="credentials.json",
        help="Path to the Google OAuth desktop client credentials JSON.",
    )
    parser.add_argument(
        "--token",
        default="token.json",
        help="Path to the stored OAuth token file.",
    )
    parser.add_argument(
        "--calendar-id",
        default="primary",
        help="Google Calendar ID to analyze. Default: primary.",
    )
    parser.add_argument(
        "--weeks",
        type=int,
        default=12,
        help="Number of weeks to include, counting back from today. Default: 12.",
    )
    parser.add_argument(
        "--timezone",
        default=DEFAULT_TIMEZONE,
        help=f"IANA timezone used for week boundaries. Default: {DEFAULT_TIMEZONE}.",
    )
    parser.add_argument(
        "--week-start",
        choices=["monday", "sunday"],
        default="monday",
        help="Week boundary to use for grouping. Default: monday.",
    )
    parser.add_argument(
        "--include-cancelled",
        action="store_true",
        help="Include cancelled events in weekly counts.",
    )
    parser.add_argument(
        "--csv",
        help="Optional path to write the weekly counts as CSV.",
    )
    parser.add_argument(
        "--list-calendars",
        action="store_true",
        help="List available calendars for the authenticated account and exit.",
    )
    return parser


def load_credentials(credentials_path: Path, token_path: Path) -> Credentials:
    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not credentials_path.exists():
                raise FileNotFoundError(
                    f"Missing OAuth credentials file: {credentials_path}. "
                    "Create a Google Cloud desktop OAuth client and save it here."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
            creds = flow.run_local_server(port=0)

        token_path.write_text(creds.to_json(), encoding="utf-8")

    return creds


def fetch_events(
    service: Any,
    calendar_id: str,
    start_at: datetime,
    end_at: datetime,
    include_cancelled: bool,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    page_token = None

    while True:
        response = (
            service.events()
            .list(
                calendarId=calendar_id,
                timeMin=start_at.isoformat(),
                timeMax=end_at.isoformat(),
                singleEvents=True,
                showDeleted=include_cancelled,
                orderBy="startTime",
                pageToken=page_token,
            )
            .execute()
        )
        events.extend(response.get("items", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return events


def list_calendars(service: Any) -> list[dict[str, str]]:
    results = []
    page_token = None
    while True:
        response = service.calendarList().list(pageToken=page_token).execute()
        for item in response.get("items", []):
            results.append(
                {
                    "id": item.get("id", ""),
                    "summary": item.get("summary", ""),
                    "primary": str(item.get("primary", False)).lower(),
                    "timeZone": item.get("timeZone", ""),
                }
            )
        page_token = response.get("nextPageToken")
        if not page_token:
            break
    return results


def floor_to_week(day: date, week_start: str) -> date:
    weekday = day.weekday()
    offset = weekday if week_start == "monday" else (weekday + 1) % 7
    return day - timedelta(days=offset)


def event_date_in_zone(event: dict[str, Any], zone: ZoneInfo) -> date:
    start = event.get("start", {})
    if "dateTime" in start:
        return datetime.fromisoformat(start["dateTime"].replace("Z", "+00:00")).astimezone(zone).date()
    if "date" in start:
        return date.fromisoformat(start["date"])
    raise ValueError(f"Event missing start date: {event.get('id', '<unknown>')}")


def count_events_per_week(
    events: list[dict[str, Any]],
    zone: ZoneInfo,
    week_start: str,
    include_cancelled: bool,
) -> Counter[date]:
    counts: Counter[date] = Counter()
    for event in events:
        if event.get("status") == "cancelled" and not include_cancelled:
            continue
        week = floor_to_week(event_date_in_zone(event, zone), week_start)
        counts[week] += 1
    return counts


def build_weekly_series(
    counts: Counter[date],
    start_day: date,
    weeks: int,
) -> list[WeeklyCount]:
    series = []
    current = start_day
    for _ in range(weeks):
        series.append(
            WeeklyCount(
                week_start=current,
                week_end=current + timedelta(days=6),
                count=counts.get(current, 0),
            )
        )
        current += timedelta(days=7)
    return series


def print_report(rows: list[WeeklyCount], calendar_id: str, timezone_name: str, week_start: str) -> None:
    total = sum(row.count for row in rows)
    average = total / len(rows) if rows else 0
    print(f"Calendar: {calendar_id}")
    print(f"Timezone: {timezone_name}")
    print(f"Week start: {week_start}")
    print(f"Weeks analyzed: {len(rows)}")
    print(f"Total events: {total}")
    print(f"Average events per week: {average:.2f}")
    print("")
    print("week_start,week_end,event_count")
    for row in rows:
        print(f"{row.week_start.isoformat()},{row.week_end.isoformat()},{row.count}")


def write_csv(rows: list[WeeklyCount], output_path: Path) -> None:
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["week_start", "week_end", "event_count"])
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "week_start": row.week_start.isoformat(),
                    "week_end": row.week_end.isoformat(),
                    "event_count": row.count,
                }
            )


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    zone = ZoneInfo(args.timezone)
    today = datetime.now(zone).date()
    window_end = datetime.combine(today + timedelta(days=1), time.min, tzinfo=zone)
    last_week_start = floor_to_week(today, args.week_start)
    first_week_start = last_week_start - timedelta(days=(args.weeks - 1) * 7)
    window_start = datetime.combine(first_week_start, time.min, tzinfo=zone)

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

    counts = count_events_per_week(
        events=events,
        zone=zone,
        week_start=args.week_start,
        include_cancelled=args.include_cancelled,
    )
    rows = build_weekly_series(counts=counts, start_day=first_week_start, weeks=args.weeks)

    if args.csv:
        write_csv(rows, Path(args.csv).expanduser().resolve())

    print_report(
        rows=rows,
        calendar_id=args.calendar_id,
        timezone_name=args.timezone,
        week_start=args.week_start,
    )


if __name__ == "__main__":
    main()
