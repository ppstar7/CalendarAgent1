# Data Analyst Agent

`data-analyst-agent` is a small local analyst assistant for tabular datasets. It loads your files into DuckDB, exposes a focused set of analysis tools to an OpenAI model, and returns concise findings, caveats, and next steps.

## What it can do

- Load `.csv`, `.tsv`, `.xlsx`, `.json`, `.jsonl`, and `.parquet`
- Inspect schemas, nulls, sample rows, and quick numeric/categorical profiles
- Run SQL over one or more loaded datasets
- Answer analyst-style questions such as trend checks, segmentation, anomaly review, and summary reporting

## Quick start

1. Create and activate a virtual environment.
2. Install the package in editable mode:

```bash
pip install -e .
```

3. Export your API key:

```bash
export OPENAI_API_KEY="your-key-here"
```

4. Ask a question against one or more datasets:

```bash
data-analyst-agent \
  --data ./sales.csv \
  --data ./customers.xlsx \
  --question "Which customer segments drive the most revenue, and what should I investigate next?"
```

## Google Calendar weekly counts

You can also connect your Google Calendar and count events per week with a read-only OAuth flow.

1. In Google Cloud, enable the Google Calendar API and create a Desktop OAuth client.
Official quickstart: [Google Calendar Python quickstart](https://developers.google.com/workspace/calendar/api/quickstart/python)
2. Download the OAuth client JSON and place it in this project as `credentials.json`.
3. Install dependencies:

```bash
pip install -e .
```

4. Run the weekly report:

```bash
calendar-weekly-report --weeks 12
```

On first run, a browser window will open for Google sign-in and consent. The script stores the resulting token in `token.json` for future runs.

Useful examples:

```bash
calendar-weekly-report --list-calendars
calendar-weekly-report --calendar-id primary --weeks 26
calendar-weekly-report --calendar-id your_calendar_id@group.calendar.google.com --csv weekly_counts.csv
calendar-weekly-report --weeks 12 --week-start sunday --timezone America/Los_Angeles
```

This tool uses the read-only scope `https://www.googleapis.com/auth/calendar.readonly`.

## Customer Success calendar review agent

There is also a job-search-focused calendar review CLI that inspects your upcoming Google Calendar events and flags which ones look helpful for landing a Customer Success role.

Run it like this:

```bash
customer-success-calendar-agent --weeks 8
```

It will:

- Count your upcoming events by week
- List the events, when they happen, and where they happen
- Score each event as `High value`, `Maybe useful`, or `Low value`
- Suggest whether to keep, review manually, or deprioritize the event

Useful examples:

```bash
customer-success-calendar-agent --list-calendars
customer-success-calendar-agent --calendar-id primary --weeks 6
customer-success-calendar-agent --calendar-id primary --weeks 8 --json customer_success_calendar_report.json
customer-success-calendar-agent --calendar-id primary --month 2026-05 --json may_report.json --pdf may_report.pdf
customer-success-calendar-agent --goal "Land a job in Customer Success at a SaaS company"
```

The scoring is heuristic and based on signals like interviews, recruiter meetings, networking, Customer Success keywords, SaaS tools, event locations, and obvious personal/low-signal keywords.

## Example prompts

- `Summarize this dataset like a senior analyst preparing a kickoff note.`
- `Find the top drivers of churn and explain what evidence supports each one.`
- `Compare Q1 vs Q2 performance by region and flag anything unusual.`
- `Write three stakeholder-ready bullets about conversion trends.`

## Useful flags

- `--table-name`: override the default table name for a dataset
- `--model`: choose a different model, default is `gpt-5`
- `--max-steps`: cap the number of tool-calling rounds
- `--profile-only`: print a local dataset overview without calling the API

## Notes

- The agent uses DuckDB for SQL, so loaded datasets become queryable tables.
- If you load multiple files without custom names, table names are derived from filenames.
- Excel files load the first sheet by default.
