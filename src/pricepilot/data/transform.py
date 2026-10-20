"""Transform stage: run the SQL files that build dimensions, staging, and fact tables."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import duckdb

from pricepilot.config import PROJECT_ROOT, DataConfig

SQL_DIR = PROJECT_ROOT / "sql"
DIMENSIONS = ["dim_calendar", "dim_product"]
FACTS = ["fact_sales", "fact_prices"]
OUTPUT_TABLES = [*DIMENSIONS, *FACTS]


def _run_sql(
    con: duckdb.DuckDBPyConnection, path: Path, params: Mapping[str, object] | None = None
) -> None:
    """Execute one SQL file with named parameters."""
    con.execute(path.read_text(), dict(params or {}))


def build_dimensions(con: duckdb.DuckDBPyConnection, cfg: DataConfig) -> None:
    """Build dim_calendar and dim_product from the raw views."""
    _run_sql(con, SQL_DIR / "marts" / "dim_calendar.sql")
    _run_sql(con, SQL_DIR / "marts" / "dim_product.sql", {"category": cfg.category})


def build_staging(con: duckdb.DuckDBPyConnection, cfg: DataConfig) -> None:
    """Build stg_movement, tagging each row as accepted or rejected with a reason."""
    params = {"min_price": cfg.price_bounds.min, "max_price": cfg.price_bounds.max}
    _run_sql(con, SQL_DIR / "staging" / "stg_movement.sql", params)


def build_facts(con: duckdb.DuckDBPyConnection, source_version: str) -> None:
    """Build fact_sales and fact_prices from accepted staging rows."""
    _run_sql(con, SQL_DIR / "marts" / "fact_sales.sql", {"source_version": source_version})
    _run_sql(con, SQL_DIR / "marts" / "fact_prices.sql")
