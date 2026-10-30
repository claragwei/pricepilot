"""Load the gzipped Dominick's category files into Postgres raw tables, verifying each file."""

from __future__ import annotations

import argparse
import os
import time
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

import psycopg2
from psycopg2 import sql
from psycopg2.extensions import connection as Connection

from pricepilot.config import WarehouseConfig, data_dir, load_warehouse_config
from pricepilot.warehouse.stream import RawStream, column_plan, open_stream

LOG_TABLE = "_load_log"


class LoadError(RuntimeError):
    """A file failed a load check; its table is rolled back."""


def connect() -> Connection:
    """Open a Postgres connection from POSTGRES_* variables, defaulting to the local container."""
    return psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=int(os.environ.get("POSTGRES_PORT", "5433")),
        user=os.environ.get("POSTGRES_USER", "pricepilot"),
        password=os.environ.get("POSTGRES_PASSWORD", "pricepilot"),
        dbname=os.environ.get("POSTGRES_DB", "pricepilot"),
    )


def read_checksums(path: Path) -> dict[str, str]:
    """Parse a sha256sum-style file into a map of relative path to hex digest."""
    sums: dict[str, str] = {}
    for line in path.read_text().splitlines():
        digest, _, name = line.partition("  ")
        if digest and name:
            sums[name.strip()] = digest
    return sums


def create_table_sql(schema: str, table: str, columns: dict[str, str]) -> sql.Composed:
    """Build the CREATE TABLE statement for one raw table."""
    cols = sql.SQL(", ").join(
        sql.SQL("{} {}").format(sql.Identifier(name.lower()), sql.SQL(kind))
        for name, kind in columns.items()
    )
    return sql.SQL("create table {} ({})").format(sql.Identifier(schema, table), cols)


def copy_sql(schema: str, table: str, columns: Iterable[str]) -> sql.Composed:
    """Build the COPY statement that reads CSV rows without a header into the given columns."""
    cols = sql.SQL(", ").join(sql.Identifier(name.lower()) for name in columns)
    return sql.SQL("copy {} ({}) from stdin with (format csv, encoding 'LATIN1')").format(
        sql.Identifier(schema, table), cols
    )


def load_file(
    con: Connection,
    cfg: WarehouseConfig,
    path: Path,
    table: str,
    kind: str,
    expected_sha: str,
) -> dict[str, Any]:
    """Load one file into a fresh table, check its hash and row count, and log the result."""
    started = time.monotonic()
    stream: RawStream = open_stream(path)
    try:
        if kind == "movement":
            keep = list(cfg.movement.keep)
            stream.keep_columns(column_plan(stream.header, keep, cfg.movement.drop))
            columns = {name: cfg.movement.keep[name] for name in keep}
        else:
            unknown = set(stream.header) - set(cfg.upc)
            if unknown:
                raise LoadError(f"{path.name}: unexpected columns {sorted(unknown)}")
            columns = {name: cfg.upc[name] for name in stream.header}
        schema = cfg.raw_schema
        with con.cursor() as cur:
            cur.execute(sql.SQL("drop table if exists {}").format(sql.Identifier(schema, table)))
            cur.execute(create_table_sql(schema, table, columns))
            cur.copy_expert(copy_sql(schema, table, columns), stream)
            cur.execute(sql.SQL("select count(*) from {}").format(sql.Identifier(schema, table)))
            row = cur.fetchone()
            loaded = int(row[0]) if row else 0
            if loaded != stream.rows:
                raise LoadError(f"{path.name}: read {stream.rows} rows, table has {loaded}")
            if stream.sha256 != expected_sha:
                raise LoadError(f"{path.name}: checksum differs from the recorded value")
            seconds = round(time.monotonic() - started, 1)
            cur.execute(
                sql.SQL(
                    "insert into {} (table_name, source_file, rows, sha256, seconds, loaded_at) "
                    "values (%s, %s, %s, %s, %s, now()) "
                    "on conflict (table_name) do update set source_file = excluded.source_file, "
                    "rows = excluded.rows, sha256 = excluded.sha256, seconds = excluded.seconds, "
                    "loaded_at = excluded.loaded_at"
                ).format(sql.Identifier(schema, LOG_TABLE)),
                (table, path.name, loaded, stream.sha256, seconds),
            )
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        stream.close()
    return {"table": table, "rows": loaded, "seconds": seconds}


def prepare_schema(con: Connection, schema: str) -> None:
    """Create the raw schema and the load log table if they do not exist."""
    with con.cursor() as cur:
        cur.execute(sql.SQL("create schema if not exists {}").format(sql.Identifier(schema)))
        cur.execute(
            sql.SQL(
                "create table if not exists {} (table_name text primary key, source_file text, "
                "rows bigint, sha256 text, seconds numeric, loaded_at timestamptz)"
            ).format(sql.Identifier(schema, LOG_TABLE))
        )
    con.commit()


def load_categories(
    cfg: WarehouseConfig, categories: Sequence[str], root: Path | None = None
) -> list[dict[str, Any]]:
    """Load the UPC and movement files of each category and return one summary per table."""
    base = root or data_dir()
    checksums = read_checksums(base / cfg.checksum_file)
    results: list[dict[str, Any]] = []
    con = connect()
    try:
        prepare_schema(con, cfg.raw_schema)
        for code in categories:
            for kind, stem in (("upc", f"upc{code}"), ("movement", f"w{code}")):
                relative = f"{code}/{stem}.csv"
                path = base / cfg.raw_dir / f"{relative}.gz"
                if relative not in checksums:
                    raise LoadError(f"no recorded checksum for {relative}")
                result = load_file(con, cfg, path, stem, kind, checksums[relative])
                print(f"{result['table']}: {result['rows']:,} rows in {result['seconds']}s")
                results.append(result)
    finally:
        con.close()
    return results


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point."""
    cfg = load_warehouse_config()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--categories", nargs="*", default=cfg.categories, help="category codes")
    args = parser.parse_args(argv)
    unknown = set(args.categories) - set(cfg.categories)
    if unknown:
        parser.error(f"unknown categories: {sorted(unknown)}")
    load_categories(cfg, args.categories)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
