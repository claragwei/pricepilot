"""Load stage: write tables to Parquet atomically, and persist the quality report and run log."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import duckdb

from pricepilot.data.transform import OUTPUT_TABLES
from pricepilot.data.validate import QualityReport

TABLE_ORDER = {
    "dim_calendar": "week",
    "dim_product": "item_id",
    "fact_sales": "item_id, store_id, week",
    "fact_prices": "item_id, store_id, week",
}


def write_parquet(con: duckdb.DuckDBPyConnection, query: str, path: Path) -> int:
    """Write a query result to Parquet via a temp file, so reruns replace output safely."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".parquet.tmp")
    con.execute(f"copy ({query}) to '{tmp}' (format parquet)")
    os.replace(tmp, path)
    row = con.execute(f"select count(*) from read_parquet('{path}')").fetchone()
    return int(row[0]) if row else 0


def load_tables(con: duckdb.DuckDBPyConnection, output_dir: Path) -> dict[str, int]:
    """Write the analytics tables to output_dir; return rows written per table."""
    counts = {}
    for table in OUTPUT_TABLES:
        query = f"select * from {table} order by {TABLE_ORDER[table]}"
        counts[table] = write_parquet(con, query, output_dir / f"{table}.parquet")
    return counts


def write_rejects(con: duckdb.DuckDBPyConnection, rejects_dir: Path) -> int:
    """Write rejected movement rows with their reasons to the interim area."""
    query = (
        "select * from stg_movement where reject_reason is not null "
        "order by item_id, store_id, week"
    )
    return write_parquet(con, query, rejects_dir / "rejected_movement.parquet")


def write_report(report: QualityReport, output_dir: Path) -> Path:
    """Write the quality report as JSON, replacing any previous one."""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "quality_report.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    os.replace(tmp, path)
    return path


def append_run_log(record: dict[str, Any], output_dir: Path) -> None:
    """Append one run record (status, timings, row counts) to run_log.jsonl."""
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "run_log.jsonl").open("a") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")
