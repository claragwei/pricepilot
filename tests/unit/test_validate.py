"""Unit tests for output validation checks and the week decode reference."""

from __future__ import annotations

import duckdb

from pricepilot.config import PROJECT_ROOT, DataConfig
from pricepilot.data.validate import validate_outputs


def build_tables(fact_sales_rows: int) -> duckdb.DuckDBPyConnection:
    """Create minimal staging and fact tables with a chosen fact_sales row count."""
    con = duckdb.connect()
    con.execute("create table raw_movement as select range as week from range(4)")
    con.execute(
        "create table stg_movement as select range as week, null::varchar as reject_reason "
        "from range(4)"
    )
    for table in ("fact_sales", "fact_prices"):
        n = fact_sales_rows if table == "fact_sales" else 4
        con.execute(
            f"create table {table} as select 1 as item_id, 1 as store_id, range as week, "
            f"date '2000-01-01' as week_start, 1 as units_sold from range({n})"
        )
    return con


def test_row_multiplication_is_detected(cfg: DataConfig) -> None:
    checks = {c.name: c for c in validate_outputs(build_tables(8), cfg)}
    assert not checks["no_row_multiplication"].passed


def test_matching_row_counts_pass(cfg: DataConfig) -> None:
    checks = {c.name: c for c in validate_outputs(build_tables(4), cfg)}
    assert checks["no_row_multiplication"].passed


def test_week_decode_reference_matches_manual() -> None:
    rows = duckdb.sql(
        "select week, week_start, event from "
        f"read_csv('{PROJECT_ROOT}/data/reference/week_decode.csv') order by week"
    ).fetchall()
    assert len(rows) == 400 and [r[0] for r in rows] == list(range(1, 401))
    by_week = {r[0]: r for r in rows}
    assert str(by_week[1][1]) == "1989-09-14"
    assert str(by_week[372][1]) == "1996-10-24" and by_week[372][2] == "Halloween"
    assert str(by_week[399][1]) == "1997-05-01"
