from __future__ import annotations

import argparse
import json
import os
import sys

from analyst_agent.agent import DataAnalystAgent
from analyst_agent.data_tools import DatasetRegistry


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a local data analyst agent on one or more datasets.")
    parser.add_argument("--data", action="append", required=True, help="Path to a dataset file.")
    parser.add_argument(
        "--table-name",
        action="append",
        default=[],
        help="Optional table name override. Order should match --data when provided.",
    )
    parser.add_argument("--question", help="Question for the analyst agent.")
    parser.add_argument("--model", default="gpt-5", help="Model to use for the agent.")
    parser.add_argument("--max-steps", type=int, default=8, help="Maximum tool-calling rounds.")
    parser.add_argument(
        "--profile-only",
        action="store_true",
        help="Print a local dataset overview and exit without calling the API.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if not args.profile_only and not args.question:
        parser.error("--question is required unless --profile-only is set.")

    if args.table_name and len(args.table_name) not in {0, len(args.data)}:
        parser.error("If provided, --table-name must be passed once per --data value.")

    registry = DatasetRegistry()
    table_names = args.table_name or [None] * len(args.data)

    for path, table_name in zip(args.data, table_names, strict=True):
        registry.load(path, table_name=table_name)

    if args.profile_only:
        print(json.dumps(registry.local_report(), indent=2))
        return

    if not os.environ.get("OPENAI_API_KEY"):
        sys.exit("OPENAI_API_KEY is not set.")

    agent = DataAnalystAgent(
        registry=registry,
        model=args.model,
        max_steps=args.max_steps,
    )
    result = agent.ask(args.question)
    print(result.answer)


if __name__ == "__main__":
    main()
