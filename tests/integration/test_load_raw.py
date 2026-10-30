"""Integration tests for the Postgres raw loader, run against the local Docker database."""

from __future__ import annotations

import gzip
import hashlib
from collections.abc import Iterator
from pathlib import Path

import psycopg2
import pytest
from psycopg2.extensions import connection as Connection

from pricepilot.config import WarehouseConfig, load_warehouse_config
from pricepilot.warehouse import load_raw

SCHEMA = "raw_test"
MOVEMENT = (
    "UPC,STORE,WEEK,MOVE,QTY,PRICE,SALE,PROFIT,OK,PRICE_HEX,PROFIT_HEX\n"
    "100,1,5,2,1,3.50,,10.5,1,aa,bb\n"
    "100,1,6,0,1,0,B,0,1,aa,bb\n"
)
UPC = 'COM_CODE,UPC,DESCRIP,SIZE,CASE,NITEM\n311,100,"CEREAL, ONE",10 OZ,12,1\n'


@pytest.fixture
def db() -> Iterator[Connection]:
    """A connection to the local Postgres, or a skip with the reason if it is not running."""
    try:
        con = load_raw.connect()
    except psycopg2.OperationalError as exc:
        pytest.skip(f"Postgres not reachable (run `docker compose up -d`): {exc}")
    yield con
    con.rollback()
    with con.cursor() as cur:
        cur.execute(f"drop schema if exists {SCHEMA} cascade")
    con.commit()
    con.close()


@pytest.fixture
def cfg() -> WarehouseConfig:
    """The warehouse config pointed at a throwaway schema."""
    return load_warehouse_config().model_copy(update={"raw_schema": SCHEMA})


def _write_source(root: Path, movement: str = MOVEMENT) -> None:
    """Write category cer's gzipped files, with a checksum file recording the standard text."""
    folder = root / "raw" / "cer"
    folder.mkdir(parents=True)
    (folder / "upccer.csv.gz").write_bytes(gzip.compress(UPC.encode()))
    (folder / "wcer.csv.gz").write_bytes(gzip.compress(movement.encode()))
    sums = [
        f"{hashlib.sha256(text.encode()).hexdigest()}  cer/{name}.csv"
        for name, text in (("upccer", UPC), ("wcer", MOVEMENT))
    ]
    (root / "raw" / "CHECKSUMS.sha256").write_text("\n".join(sums) + "\n")


def test_loader_creates_typed_tables_and_logs_hashes(
    db: Connection, cfg: WarehouseConfig, tmp_path: Path
) -> None:
    """Both files load with the right row counts, canonical columns, and a log entry each."""
    _write_source(tmp_path)
    load_raw.load_categories(cfg, ["cer"], root=tmp_path)
    with db.cursor() as cur:
        cur.execute(f"select store, upc, week, move, price, sale from {SCHEMA}.wcer order by week")
        assert cur.fetchall() == [(1, 100, 5, 2, 3.5, None), (1, 100, 6, 0, 0, "B")]
        cur.execute(f"select descrip from {SCHEMA}.upccer")
        assert cur.fetchone() == ("CEREAL, ONE",)
        cur.execute(f"select table_name, rows from {SCHEMA}._load_log order by table_name")
        assert cur.fetchall() == [("upccer", 1), ("wcer", 2)]


def test_checksum_mismatch_rolls_back_the_table(
    db: Connection, cfg: WarehouseConfig, tmp_path: Path
) -> None:
    """A file that differs from its recorded hash fails and leaves no table behind."""
    _write_source(tmp_path, movement=MOVEMENT + "100,1,7,1,1,2.00,,5,1,aa,bb\n")
    with pytest.raises(load_raw.LoadError, match="checksum"):
        load_raw.load_categories(cfg, ["cer"], root=tmp_path)
    with db.cursor() as cur:
        cur.execute("select to_regclass(%s)", (f"{SCHEMA}.wcer",))
        assert cur.fetchone() == (None,)
