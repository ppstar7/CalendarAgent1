from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd


READ_ONLY_SQL = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)


def _slugify(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    return text or "dataset"


def _coerce_value(value: Any) -> Any:
    if pd.isna(value):
        return None
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except TypeError:
            return str(value)
    if isinstance(value, (int, float, str, bool)) or value is None:
        return value
    return str(value)


@dataclass
class LoadedDataset:
    table_name: str
    source_path: str
    row_count: int
    column_count: int
    columns: list[str]


class DatasetRegistry:
    def __init__(self) -> None:
        self.connection = duckdb.connect(database=":memory:")
        self.datasets: dict[str, LoadedDataset] = {}
        self.frames: dict[str, pd.DataFrame] = {}

    def load(self, path: str, table_name: str | None = None) -> LoadedDataset:
        source = Path(path).expanduser().resolve()
        if not source.exists():
            raise FileNotFoundError(f"Dataset not found: {source}")

        table = _slugify(table_name or source.stem)
        if table in self.datasets:
            raise ValueError(f"Table name already loaded: {table}")

        frame = self._read_frame(source)
        self.connection.register(f"{table}__frame", frame)
        self.connection.execute(f"create table {table} as select * from {table}__frame")
        self.connection.unregister(f"{table}__frame")

        dataset = LoadedDataset(
            table_name=table,
            source_path=str(source),
            row_count=len(frame.index),
            column_count=len(frame.columns),
            columns=[str(column) for column in frame.columns.tolist()],
        )
        self.datasets[table] = dataset
        self.frames[table] = frame
        return dataset

    def _read_frame(self, source: Path) -> pd.DataFrame:
        suffix = source.suffix.lower()
        if suffix == ".csv":
            return pd.read_csv(source)
        if suffix == ".tsv":
            return pd.read_csv(source, sep="\t")
        if suffix in {".xlsx", ".xls"}:
            return pd.read_excel(source)
        if suffix == ".json":
            return pd.read_json(source)
        if suffix == ".jsonl":
            return pd.read_json(source, lines=True)
        if suffix == ".parquet":
            return pd.read_parquet(source)
        raise ValueError(f"Unsupported dataset format: {suffix}")

    def list_datasets(self) -> list[dict[str, Any]]:
        return [
            {
                "table_name": dataset.table_name,
                "source_path": dataset.source_path,
                "row_count": dataset.row_count,
                "column_count": dataset.column_count,
                "columns": dataset.columns,
            }
            for dataset in self.datasets.values()
        ]

    def schema(self, table_name: str) -> dict[str, Any]:
        frame = self._require_table(table_name)
        return {
            "table_name": table_name,
            "columns": [
                {
                    "name": str(column),
                    "dtype": str(dtype),
                    "null_count": int(frame[column].isna().sum()),
                }
                for column, dtype in frame.dtypes.items()
            ],
            "row_count": int(len(frame.index)),
        }

    def preview(self, table_name: str, limit: int = 5) -> dict[str, Any]:
        frame = self._require_table(table_name)
        rows = frame.head(limit).to_dict(orient="records")
        return {
            "table_name": table_name,
            "rows": [{key: _coerce_value(value) for key, value in row.items()} for row in rows],
        }

    def profile(self, table_name: str) -> dict[str, Any]:
        frame = self._require_table(table_name)
        numeric_columns = frame.select_dtypes(include=["number"]).columns.tolist()
        categorical_columns = frame.select_dtypes(exclude=["number"]).columns.tolist()

        numeric_summary = {}
        if numeric_columns:
            describe = frame[numeric_columns].describe().transpose().reset_index()
            for row in describe.to_dict(orient="records"):
                column = row.pop("index")
                numeric_summary[str(column)] = {key: _coerce_value(value) for key, value in row.items()}

        categorical_summary = {}
        for column in categorical_columns[:10]:
            top_values = frame[column].astype("string").fillna("<NULL>").value_counts().head(5)
            categorical_summary[str(column)] = [
                {"value": str(index), "count": int(count)} for index, count in top_values.items()
            ]

        return {
            "table_name": table_name,
            "row_count": int(len(frame.index)),
            "column_count": int(len(frame.columns)),
            "null_counts": {str(column): int(frame[column].isna().sum()) for column in frame.columns},
            "numeric_summary": numeric_summary,
            "categorical_summary": categorical_summary,
        }

    def query(self, sql: str, limit: int = 200) -> dict[str, Any]:
        cleaned_sql = sql.strip().rstrip(";")
        if not READ_ONLY_SQL.match(cleaned_sql):
            raise ValueError("Only read-only SELECT or WITH queries are allowed.")

        limited_sql = f"select * from ({cleaned_sql}) as analyst_query limit {int(limit)}"
        result = self.connection.execute(limited_sql).fetch_df()
        rows = result.to_dict(orient="records")
        return {
            "sql": cleaned_sql,
            "row_count": int(len(result.index)),
            "columns": [str(column) for column in result.columns.tolist()],
            "rows": [{key: _coerce_value(value) for key, value in row.items()} for row in rows],
        }

    def overview_text(self) -> str:
        payload = {"datasets": self.list_datasets()}
        return json.dumps(payload, indent=2)

    def local_report(self) -> dict[str, Any]:
        return {
            "datasets": [
                {
                    **dataset,
                    "schema": self.schema(dataset["table_name"]),
                    "profile": self.profile(dataset["table_name"]),
                }
                for dataset in self.list_datasets()
            ]
        }

    def _require_table(self, table_name: str) -> pd.DataFrame:
        if table_name not in self.frames:
            available = ", ".join(sorted(self.frames))
            raise KeyError(f"Unknown table '{table_name}'. Available tables: {available}")
        return self.frames[table_name]
