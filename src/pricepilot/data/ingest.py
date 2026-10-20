"""Extract stage: locate source files, record checksums, and expose them as DuckDB views."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb

from pricepilot.config import DataConfig

MOVEMENT_TYPES = {
    "STORE": "INTEGER",
    "UPC": "BIGINT",
    "WEEK": "INTEGER",
    "MOVE": "INTEGER",
    "QTY": "INTEGER",
    "PRICE": "DOUBLE",
    "SALE": "VARCHAR",
    "PROFIT": "DOUBLE",
    "OK": "INTEGER",
}
UPC_COLUMNS = {"COM_CODE", "UPC", "DESCRIP", "SIZE", "CASE", "NITEM"}
WEEK_DECODE_COLUMNS = {"week", "week_start", "week_end", "event"}


class IngestError(Exception):
    """Raised when source files are missing, malformed, or unreadable."""


@dataclass(frozen=True)
class SourceFiles:
    """Paths and provenance of the input files for one run."""

    movement: Path
    upc: Path
    week_decode: Path
    source_version: str
    manifest: dict[str, dict[str, Any]]


def file_sha256(path: Path) -> str:
    """Return the SHA-256 hex digest of a file, read in chunks."""
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def locate_sources(cfg: DataConfig, root: Path) -> SourceFiles:
    """Find the configured input files and record size, checksum, and modified time."""
    movement = root / cfg.source_dir / cfg.movement_file
    upc = root / cfg.source_dir / cfg.upc_file
    week_decode = root / cfg.week_decode_file
    missing = [str(p) for p in (movement, upc, week_decode) if not p.is_file()]
    if missing:
        raise IngestError(
            "Missing required input file(s): " + ", ".join(missing) + ". "
            "See docs/DATA_DICTIONARY.md for where to obtain them."
        )
    manifest: dict[str, dict[str, Any]] = {}
    for name, path in (("movement", movement), ("upc", upc), ("week_decode", week_decode)):
        stat = path.stat()
        manifest[name] = {
            "path": str(path),
            "bytes": stat.st_size,
            "sha256": file_sha256(path),
            "modified_at": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
        }
    version = f"{cfg.category}-{manifest['movement']['sha256'][:12]}"
    return SourceFiles(movement, upc, week_decode, version, manifest)


def _quote(value: Path | str) -> str:
    """Quote a value as a SQL string literal."""
    return "'" + str(value).replace("'", "''") + "'"


def _check_columns(
    con: duckdb.DuckDBPyConnection, read_sql: str, required: set[str], label: str
) -> None:
    """Fail clearly if a CSV lacks any required column."""
    try:
        found = {c.upper() for c in con.sql(f"select * from {read_sql} limit 0").columns}
    except duckdb.Error as exc:
        raise IngestError(f"Cannot read {label} file: {exc}") from exc
    absent = sorted(c for c in required if c.upper() not in found)
    if absent:
        raise IngestError(f"{label} file is missing required column(s): {', '.join(absent)}")


def register_raw(
    con: duckdb.DuckDBPyConnection, sources: SourceFiles, cfg: DataConfig, sample: bool = False
) -> None:
    """Create raw_movement, raw_upc, and raw_week_decode views over the source CSVs."""
    types = ", ".join(f"{k!r}: {v!r}" for k, v in MOVEMENT_TYPES.items())
    movement_read = f"read_csv({_quote(sources.movement)}, header=true, types={{{types}}})"
    upc_read = f"read_csv({_quote(sources.upc)}, header=true, encoding='latin-1')"
    week_read = f"read_csv({_quote(sources.week_decode)}, header=true)"

    _check_columns(
        con, f"read_csv({_quote(sources.movement)}, header=true)", set(MOVEMENT_TYPES), "movement"
    )
    _check_columns(con, upc_read, UPC_COLUMNS, "UPC")
    _check_columns(con, week_read, WEEK_DECODE_COLUMNS, "week decode")

    where = ""
    if sample:
        stores = ", ".join(str(int(s)) for s in cfg.sample.stores)
        where = (
            f" where store in ({stores})"
            f" and week between {int(cfg.sample.first_week)} and {int(cfg.sample.last_week)}"
        )
    try:
        con.execute(f"create or replace view raw_movement as select * from {movement_read}{where}")
        con.execute(f"create or replace view raw_upc as select * from {upc_read}")
        con.execute(f"create or replace view raw_week_decode as select * from {week_read}")
        scan = ", ".join(f"max({c})" for c in MOVEMENT_TYPES if c != "SALE")
        con.execute(f"select {scan} from raw_movement").fetchone()
    except duckdb.Error as exc:
        raise IngestError(f"Source data has unexpected values or types: {exc}") from exc
