# Prat Calendar Agent

This project is a local Python calendar-analysis agent built to help review Google Calendar events and judge whether they support the goal:

`Land a job in Customer Success`

It can:

- connect to Google Calendar with read-only OAuth
- count events by week
- review upcoming events for job-search relevance
- analyze a specific month such as `2026-05`
- export reports as terminal output, `JSON`, and `PDF`

This repo also still contains the original tabular data analyst scaffold that was created first, but the main focus of the project is now calendar analysis.

## Project Location

Main working folder:

[/Users/kalu/Documents/Prat-Calendar Agent](/Users/kalu/Documents/Prat-Calendar%20Agent)

This repo was moved here from an earlier workspace called `New project`, and this folder is now the canonical version.

## What Was Built

### 1. Data analyst scaffold

These files were created first:

- [/Users/kalu/Documents/Prat-Calendar Agent/analyst_agent/agent.py](/Users/kalu/Documents/Prat-Calendar%20Agent/analyst_agent/agent.py)
- [/Users/kalu/Documents/Prat-Calendar Agent/analyst_agent/cli.py](/Users/kalu/Documents/Prat-Calendar%20Agent/analyst_agent/cli.py)
- [/Users/kalu/Documents/Prat-Calendar Agent/analyst_agent/data_tools.py](/Users/kalu/Documents/Prat-Calendar%20Agent/analyst_agent/data_tools.py)

Purpose:

- load CSV, TSV, Excel, JSON, JSONL, and Parquet files
- inspect schema and profiles
- run SQL through DuckDB
- answer analysis questions through OpenAI

### 2. Google Calendar weekly report tool

File:

- [/Users/kalu/Documents/Prat-Calendar Agent/analyst_agent/google_calendar_weekly.py](/Users/kalu/Documents/Prat-Calendar%20Agent/analyst_agent/google_calendar_weekly.py)

Purpose:

- authenticate with Google Calendar
- list calendars
- count events by week
- export weekly counts

Command:

```bash
calendar-weekly-report
```

### 3. Customer Success calendar review agent

File:

- [/Users/kalu/Documents/Prat-Calendar Agent/analyst_agent/customer_success_calendar_agent.py](/Users/kalu/Documents/Prat-Calendar%20Agent/analyst_agent/customer_success_calendar_agent.py)

Purpose:

- inspect upcoming or month-specific calendar events
- classify them for usefulness to a Customer Success job search
- output weekly counts and detailed event review
- export `JSON`
- export `PDF`

Command:

```bash
customer-success-calendar-agent
```

## Key Features

The Customer Success calendar agent currently supports:

- `--list-calendars`
- `--calendar-id primary`
- `--weeks N`
- `--month YYYY-MM`
- `--json output.json`
- `--pdf output.pdf`
- `--goal "custom goal"`
- `--include-cancelled`
- `--week-start monday|sunday`
- `--timezone America/Los_Angeles`

## Google Calendar Connection

This project uses the Google Calendar read-only OAuth scope:

`https://www.googleapis.com/auth/calendar.readonly`

### Files used for connection

- [/Users/kalu/Documents/Prat-Calendar Agent/credentials.json](/Users/kalu/Documents/Prat-Calendar%20Agent/credentials.json)
  This is the Google OAuth Desktop App client file downloaded from Google Cloud.

- [/Users/kalu/Documents/Prat-Calendar Agent/token.json](/Users/kalu/Documents/Prat-Calendar%20Agent/token.json)
  This is created after first successful login and stores the local OAuth token.

### Important security note

These files are private and should not be committed to GitHub:

- `credentials.json`
- `token.json`

They are ignored by git through:

- [/Users/kalu/Documents/Prat-Calendar Agent/.gitignore](/Users/kalu/Documents/Prat-Calendar%20Agent/.gitignore)

### Google Cloud / OAuth setup that was completed

The connection flow required:

- enabling the Google Calendar API
- creating a Desktop OAuth client in Google Cloud
- setting the app audience to `External`
- leaving publishing status in `Testing`
- adding your Google account as a `Test user`

That last step was necessary because Google blocked access until the testing app explicitly allowed your account.

## Generated Reports

### Initial calendar review outputs

- [/Users/kalu/Documents/Prat-Calendar Agent/customer_success_calendar_report.json](/Users/kalu/Documents/Prat-Calendar%20Agent/customer_success_calendar_report.json)

### May 2026 report outputs

- [/Users/kalu/Documents/Prat-Calendar Agent/may_2026_customer_success_calendar_report.json](/Users/kalu/Documents/Prat-Calendar%20Agent/may_2026_customer_success_calendar_report.json)
- [/Users/kalu/Documents/Prat-Calendar Agent/may_2026_customer_success_calendar_report.pdf](/Users/kalu/Documents/Prat-Calendar%20Agent/may_2026_customer_success_calendar_report.pdf)
- [/Users/kalu/Documents/Prat-Calendar Agent/may_2026_categorized_calendar_summary.pdf](/Users/kalu/Documents/Prat-Calendar%20Agent/may_2026_categorized_calendar_summary.pdf)

### What the May 2026 reports found

For May 1 through May 31, 2026:

- `14` total events
- `0` high-value events
- `4` maybe-useful events
- `10` low-value events
- `28.6%` helpful share

The deeper categorized pass grouped those May events into:

- `6` Luma sign-ups
- `5` self-added professional/community events
- `1` household / Amex task
- `1` home-admin event
- `1` birthday reminder

It also identified:

- a likely duplicate `Circle Leader Training` entry
- several Luma events that were interesting but not strongly tied to Customer Success hiring

## GitHub Status

This repo was initialized locally and connected to:

- `https://github.com/ppstar7/test.git`

Current branch:

- `main`

Initial commit:

- `27fa7a0`
- `Initial calendar agent commit`

The branch was successfully published online and is tracking `origin/main`.

## Dependencies

Defined in:

- [/Users/kalu/Documents/Prat-Calendar Agent/pyproject.toml](/Users/kalu/Documents/Prat-Calendar%20Agent/pyproject.toml)

Key packages:

- `duckdb`
- `google-api-python-client`
- `google-auth-httplib2`
- `google-auth-oauthlib`
- `openai`
- `openpyxl`
- `pandas`
- `pyarrow`
- `reportlab`

## CLI Commands

### List calendars

```bash
cd "/Users/kalu/Documents/Prat-Calendar Agent"
python3 -m analyst_agent.customer_success_calendar_agent --list-calendars
```

### Review upcoming weeks

```bash
cd "/Users/kalu/Documents/Prat-Calendar Agent"
python3 -m analyst_agent.customer_success_calendar_agent --calendar-id primary --weeks 8 --json customer_success_calendar_report.json
```

### Review a specific month

```bash
cd "/Users/kalu/Documents/Prat-Calendar Agent"
python3 -m analyst_agent.customer_success_calendar_agent --calendar-id primary --month 2026-05 --json may_2026_customer_success_calendar_report.json --pdf may_2026_customer_success_calendar_report.pdf
```

### Generate the categorized May-style summary again

The categorized PDF was generated as a custom follow-up analysis based on the May JSON output. If needed, that same summary logic can be rebuilt or folded into the main script later.

## Output Interpretation

The main report contains:

- `summary`
- `weekly_summary`
- `events`

Important event fields:

- `title`
- `start`
- `location`
- `verdict`
- `action`
- `reasons`
- `organizer`
- `attendees`

Current verdict logic:

- `High value`
  Strong match to job-search or Customer Success signals

- `Maybe useful`
  Could support networking, training, community building, or adjacent skills

- `Low value`
  Mostly personal, indirect, or weakly related to the target goal

## Current Limitations

- scoring is heuristic, not perfect
- the agent does not directly edit calendar invites
- PDF export currently focuses on reporting, not visual dashboards
- categorized summary logic for May was created as a custom one-off report and is not yet fully integrated into the main CLI as a dedicated mode
- Python on this Mac is `3.9`, which works, but newer Google libraries warn that `3.10+` would be better

## Recommended Next Improvements

- add a first-class `categorize` mode directly into `customer_success_calendar_agent.py`
- add output buckets such as `keep`, `decline`, `archive`, and `attend only if free`
- add duplicate-event detection directly in the CLI
- add organizer/source grouping in the standard report
- add a CSV export option for the job-search review agent
- add a stronger Customer Success keyword model tuned to your actual target companies and event preferences

## Files To Know

- [/Users/kalu/Documents/Prat-Calendar Agent/README.md](/Users/kalu/Documents/Prat-Calendar%20Agent/README.md)
- [/Users/kalu/Documents/Prat-Calendar Agent/pyproject.toml](/Users/kalu/Documents/Prat-Calendar%20Agent/pyproject.toml)
- [/Users/kalu/Documents/Prat-Calendar Agent/.gitignore](/Users/kalu/Documents/Prat-Calendar%20Agent/.gitignore)
- [/Users/kalu/Documents/Prat-Calendar Agent/analyst_agent/agent.py](/Users/kalu/Documents/Prat-Calendar%20Agent/analyst_agent/agent.py)
- [/Users/kalu/Documents/Prat-Calendar Agent/analyst_agent/cli.py](/Users/kalu/Documents/Prat-Calendar%20Agent/analyst_agent/cli.py)
- [/Users/kalu/Documents/Prat-Calendar Agent/analyst_agent/data_tools.py](/Users/kalu/Documents/Prat-Calendar%20Agent/analyst_agent/data_tools.py)
- [/Users/kalu/Documents/Prat-Calendar Agent/analyst_agent/google_calendar_weekly.py](/Users/kalu/Documents/Prat-Calendar%20Agent/analyst_agent/google_calendar_weekly.py)
- [/Users/kalu/Documents/Prat-Calendar Agent/analyst_agent/customer_success_calendar_agent.py](/Users/kalu/Documents/Prat-Calendar%20Agent/analyst_agent/customer_success_calendar_agent.py)

## Short Handoff

If you come back to this project later, the main thing to remember is:

1. Open the repo in [/Users/kalu/Documents/Prat-Calendar Agent](/Users/kalu/Documents/Prat-Calendar%20Agent)
2. Keep `credentials.json` and `token.json` private
3. Use `customer_success_calendar_agent.py` for calendar review
4. Use `--month YYYY-MM` for month-specific analysis
5. Use `--pdf` when you want a shareable report
