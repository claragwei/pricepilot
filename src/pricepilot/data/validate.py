"""Validate stage: data-quality checks on raw inputs and built tables, plus the report object."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import duckdb

from pricepilot.config import DataConfig


@dataclass
class Check:
    """Result of one data-quality check; required checks stop the pipeline when they fail."""

    name: str
    passed: bool
    required: bool
    detail: str


@dataclass
class QualityReport:
    """All checks and summary statistics for one pipeline run."""

    source_version: str
    checks: list[Check] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)

    def failed_required(self) -> list[Check]:
        """Return required checks that did not pass."""
        return [c for c in self.checks if c.required and not c.passed]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable view of the report."""
        return asdict(self)


def _scalar(con: duckdb.DuckDBPyConnection, sql: str) -> int:
    """Run a query returning one integer."""
    row = con.execute(sql).fetchone()
    return int(row[0]) if row and row[0] is not None else 0


def _text(con: duckdb.DuckDBPyConnection, sql: str) -> str:
    """Run a query returning one value and return it as text."""
    row = con.execute(sql).fetchone()
    return str(row[0]) if row else ""


def _zero_check(
    con: duckdb.DuckDBPyConnection, name: str, sql: str, what: str, required: bool = True
) -> Check:
    """Build a check that passes when the query returns zero offending rows."""
    n = _scalar(con, sql)
    return Check(name, n == 0, required, f"{n} {what}" if n else "ok")


def validate_inputs(con: duckdb.DuckDBPyConnection) -> list[Check]:
    """Check keys, grain, calendar coverage, and product coverage on the raw views."""
    return [
        _zero_check(
            con,
            "movement_grain_unique",
            "select count(*) from (select 1 from raw_movement group by store, upc, week "
            "having count(*) > 1)",
            "duplicated (store, upc, week) keys",
        ),
        _zero_check(
            con,
            "upc_key_unique",
            "select count(*) - count(distinct upc) from raw_upc",
            "duplicate UPC rows",
        ),
        _zero_check(
            con,
            "calendar_week_unique",
            "select count(*) - count(distinct week) from dim_calendar",
            "duplicate calendar weeks",
        ),
        _zero_check(
            con,
            "weeks_in_calendar",
            "select count(*) from raw_movement where week not in (select week from dim_calendar)",
            "movement rows with a week missing from the calendar",
        ),
        _zero_check(
            con,
            "upcs_in_product_dim",
            "select count(*) from raw_movement where upc not in (select item_id from dim_product)",
            "movement rows whose UPC is missing from the UPC file",
        ),
        _zero_check(
            con,
            "no_negative_units",
            "select count(*) from raw_movement where move < 0",
            "rows with negative units (rejected as invalid_value)",
            required=False,
        ),
    ]


def validate_outputs(con: duckdb.DuckDBPyConnection, cfg: DataConfig) -> list[Check]:
    """Check grain, key completeness, row counts, and reject rate on the built tables."""
    raw_rows = _scalar(con, "select count(*) from raw_movement")
    stg_rows = _scalar(con, "select count(*) from stg_movement")
    accepted = _scalar(con, "select count(*) from stg_movement where reject_reason is null")
    sales_rows = _scalar(con, "select count(*) from fact_sales")
    price_rows = _scalar(con, "select count(*) from fact_prices")
    rejected = stg_rows - accepted
    reject_rate = rejected / stg_rows if stg_rows else 0.0

    checks = [
        Check(
            "no_row_multiplication",
            stg_rows == raw_rows and accepted == sales_rows == price_rows,
            True,
            f"raw={raw_rows} staged={stg_rows} accepted={accepted} "
            f"fact_sales={sales_rows} fact_prices={price_rows}",
        ),
        Check(
            "reject_rate_within_limit",
            reject_rate <= cfg.max_reject_rate,
            True,
            f"{reject_rate:.3f} (limit {cfg.max_reject_rate})",
        ),
        Check("input_not_empty", raw_rows > 0, True, f"{raw_rows} rows"),
    ]
    for table in ("fact_sales", "fact_prices"):
        checks.append(
            _zero_check(
                con,
                f"{table}_grain_unique",
                f"select count(*) from (select 1 from {table} group by item_id, store_id, week "
                "having count(*) > 1)",
                "duplicated (item_id, store_id, week) keys",
            )
        )
        checks.append(
            _zero_check(
                con,
                f"{table}_keys_not_null",
                f"select count(*) from {table} where item_id is null or store_id is null "
                "or week is null or week_start is null",
                "rows with a null key or date",
            )
        )
    checks.append(
        _zero_check(
            con,
            "units_positive",
            "select count(*) from fact_sales where units_sold <= 0",
            "accepted rows with non-positive units",
        )
    )
    return checks


def collect_stats(con: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    """Summarize row counts, rejection reasons, promotion codes, and cost missingness."""
    reasons = con.execute(
        "select coalesce(reject_reason, 'accepted'), count(*) from stg_movement "
        "group by 1 order by 1"
    ).fetchall()
    promos = con.execute(
        "select coalesce(promo_code, 'none'), count(*) from stg_movement "
        "where reject_reason is null group by 1 order by 1"
    ).fetchall()
    return {
        "input_rows": _scalar(con, "select count(*) from stg_movement"),
        "row_status": {str(k): int(v) for k, v in reasons},
        "promo_codes_accepted_rows": {str(k): int(v) for k, v in promos},
        "fact_prices_null_unit_cost": _scalar(
            con, "select count(*) from fact_prices where unit_cost is null"
        ),
        "fact_prices_negative_margin": _scalar(
            con, "select count(*) from fact_prices where gross_margin_pct < 0"
        ),
        "stores": _scalar(con, "select count(distinct store_id) from fact_sales"),
        "items": _scalar(con, "select count(distinct item_id) from fact_sales"),
        "first_week_start": _text(con, "select min(week_start) from fact_sales"),
        "last_week_start": _text(con, "select max(week_start) from fact_sales"),
    }
