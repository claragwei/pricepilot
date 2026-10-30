"""Unit tests for the raw-file stream: column matching, hashing, and row counting."""

from __future__ import annotations

import gzip
import hashlib
import io
from pathlib import Path

import pytest

from pricepilot.warehouse import stream
from pricepilot.warehouse.stream import RawStream, column_plan, open_stream

KEEP = ["STORE", "UPC", "WEEK", "MOVE", "QTY", "PRICE", "SALE", "PROFIT", "OK"]
DROP = ["PRICE_HEX", "PROFIT_HEX"]
TAIL = ",SALE,PROFIT,OK,PRICE_HEX,PROFIT_HEX"


def _gz(tmp_path: Path, text: str) -> Path:
    """Write text as a gzipped file and return its path."""
    path = tmp_path / "f.csv.gz"
    path.write_bytes(gzip.compress(text.encode()))
    return path


def test_column_plan_matches_by_name_across_orders() -> None:
    """Files with UPC first, or PRICE before QTY, map to the same output order."""
    standard = ["STORE", "UPC", "WEEK", "MOVE", "QTY", "PRICE", "SALE", "PROFIT", "OK", *DROP]
    upc_first = ["UPC", "STORE", "WEEK", "MOVE", "QTY", "PRICE", "SALE", "PROFIT", "OK", *DROP]
    price_first = ["STORE", "UPC", "WEEK", "MOVE", "PRICE", "QTY", "SALE", "PROFIT", "OK", *DROP]
    assert column_plan(standard, KEEP, DROP) == [0, 1, 2, 3, 4, 5, 6, 7, 8]
    assert column_plan(upc_first, KEEP, DROP)[:2] == [1, 0]
    assert column_plan(price_first, KEEP, DROP)[4:6] == [5, 4]


def test_column_plan_rejects_unknown_or_missing_columns() -> None:
    """A header with an extra or absent column fails instead of loading silently."""
    with pytest.raises(ValueError, match="unexpected"):
        column_plan([*KEEP, "SURPRISE"], KEEP, DROP)
    with pytest.raises(ValueError, match="missing"):
        column_plan(KEEP[:-1], KEEP, DROP)


def test_stream_reorders_columns_and_drops_hex(tmp_path: Path) -> None:
    """A UPC-first file comes out in canonical order without the hex columns."""
    text = "UPC,STORE,WEEK,MOVE,QTY,PRICE" + TAIL + "\n" + "100,1,5,2,1,3.50,,10,1,aa,bb\n"
    s = open_stream(_gz(tmp_path, text))
    s.keep_columns(column_plan(s.header, KEEP, DROP))
    assert s.read() == b"1,100,5,2,1,3.50,,10,1\n"
    assert s.rows == 1
    s.close()


def test_stream_hash_covers_the_whole_decompressed_file(tmp_path: Path) -> None:
    """The digest equals SHA-256 of the original text, including the header and a CRLF file."""
    text = "A,B\r\n1,2\r\n3,4\r\n"
    s = open_stream(_gz(tmp_path, text))
    assert s.read() == b"1,2\n3,4\n"
    assert s.sha256 == hashlib.sha256(text.encode()).hexdigest()
    assert s.rows == 2
    s.close()


def test_stream_handles_chunk_boundaries_and_missing_final_newline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lines split across chunks stay whole, and the last line counts without a newline."""
    monkeypatch.setattr(stream, "CHUNK_BYTES", 5)
    rows = [f"{i},{i * 2}" for i in range(50)]
    raw = io.BytesIO(("A,B\n" + "\n".join(rows)).encode())
    s = RawStream(raw)
    out = b""
    while piece := s.read(7):
        out += piece
    assert out.decode().splitlines() == rows
    assert s.rows == 50


def test_readline_returns_one_line_at_a_time() -> None:
    """readline gives successive lines, then empty bytes at the end."""
    s = RawStream(io.BytesIO(b"A,B\n1,2\n3,4\n"))
    assert s.readline() == b"1,2\n"
    assert s.readline() == b"3,4\n"
    assert s.readline() == b""
