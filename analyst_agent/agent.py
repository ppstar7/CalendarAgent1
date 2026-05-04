from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Callable

from openai import OpenAI

from analyst_agent.data_tools import DatasetRegistry


SYSTEM_PROMPT = """
You are a senior data analyst agent.

Work like a careful analyst:
- Start from the available dataset context and inspect before concluding.
- Use tools to verify claims, especially for counts, trends, and comparisons.
- Prefer SQL for aggregations, joins, filtering, and ranking.
- Call out assumptions, data quality issues, missing context, and uncertainty.
- Give concise stakeholder-ready takeaways followed by evidence.
- Never fabricate columns, tables, or results that tools did not return.
""".strip()


def _json(data: Any) -> str:
    return json.dumps(data, indent=2, default=str)


@dataclass
class AgentResult:
    answer: str
    steps_used: int


class DataAnalystAgent:
    def __init__(
        self,
        registry: DatasetRegistry,
        model: str = "gpt-5",
        max_steps: int = 8,
        client: OpenAI | None = None,
    ) -> None:
        self.registry = registry
        self.model = model
        self.max_steps = max_steps
        self.client = client or OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        self.tool_map: dict[str, Callable[..., Any]] = {
            "list_datasets": self.registry.list_datasets,
            "describe_dataset": self.registry.schema,
            "preview_rows": self.registry.preview,
            "profile_dataset": self.registry.profile,
            "run_sql": self.registry.query,
        }

    def ask(self, question: str) -> AgentResult:
        response = self.client.responses.create(
            model=self.model,
            instructions=SYSTEM_PROMPT,
            input=[
                {
                    "role": "user",
                    "content": (
                        "Available datasets:\n"
                        f"{self.registry.overview_text()}\n\n"
                        f"Question: {question}"
                    ),
                }
            ],
            tools=self._tool_specs(),
            parallel_tool_calls=False,
        )

        steps = 1
        while steps <= self.max_steps:
            tool_outputs = []
            for item in response.output:
                if getattr(item, "type", None) != "function_call":
                    continue

                tool_name = item.name
                arguments = json.loads(item.arguments or "{}")
                result = self._call_tool(tool_name, arguments)
                tool_outputs.append(
                    {
                        "type": "function_call_output",
                        "call_id": item.call_id,
                        "output": _json(result),
                    }
                )

            if not tool_outputs:
                return AgentResult(answer=response.output_text, steps_used=steps)

            response = self.client.responses.create(
                model=self.model,
                instructions=SYSTEM_PROMPT,
                previous_response_id=response.id,
                input=tool_outputs,
                tools=self._tool_specs(),
                parallel_tool_calls=False,
            )
            steps += 1

        raise RuntimeError("Agent hit the maximum number of reasoning steps before reaching an answer.")

    def _call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        if tool_name not in self.tool_map:
            raise KeyError(f"Unknown tool requested by model: {tool_name}")
        try:
            return self.tool_map[tool_name](**arguments)
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc), "tool_name": tool_name, "arguments": arguments}

    def _tool_specs(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "name": "list_datasets",
                "description": "List all loaded datasets and their basic metadata.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
                "strict": True,
            },
            {
                "type": "function",
                "name": "describe_dataset",
                "description": "Inspect schema, row count, and per-column null counts for a table.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "table_name": {
                            "type": "string",
                            "description": "Loaded table name to inspect.",
                        }
                    },
                    "required": ["table_name"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
            {
                "type": "function",
                "name": "preview_rows",
                "description": "Preview a small number of rows from a loaded table.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "table_name": {
                            "type": "string",
                            "description": "Loaded table name to preview.",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Number of rows to preview.",
                            "minimum": 1,
                            "maximum": 20,
                        },
                    },
                    "required": ["table_name"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
            {
                "type": "function",
                "name": "profile_dataset",
                "description": "Return a quick profile with null counts, numeric summary, and top categorical values.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "table_name": {
                            "type": "string",
                            "description": "Loaded table name to profile.",
                        }
                    },
                    "required": ["table_name"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
            {
                "type": "function",
                "name": "run_sql",
                "description": "Run read-only SQL against the loaded DuckDB tables. Use for joins, grouping, filtering, trends, and comparisons.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "sql": {
                            "type": "string",
                            "description": "A read-only SQL query that references loaded table names.",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of rows to return.",
                            "minimum": 1,
                            "maximum": 500,
                        },
                    },
                    "required": ["sql"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
        ]
