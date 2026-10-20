"""Test helpers: a tiny Dominick's-style dataset written to a temporary data directory."""

from __future__ import annotations

import shutil
from pathlib import Path

from pricepilot.config import PROJECT_ROOT

MOVEMENT_HEADER = "STORE,UPC,WEEK,MOVE,QTY,PRICE,SALE,PROFIT,OK,PRICE_HEX,PROFIT_HEX"
MOVEMENT_ROWS = [
    "1,100,1,5,1,2.00,,25.0,1,0,0",
    "1,100,2,6,3,3.00,B,30.0,1,0,0",
    "1,100,3,0,1,0,,0,1,0,0",
    "1,100,4,4,1,2.00,,10.0,0,0,0",
    "1,100,5,3,1,0,,10.0,1,0,0",
    "1,100,6,2,1,2.00,,0,1,0,0",
    "1,100,7,2,1,2.00,S,-10.0,1,0,0",
    "2,200,1,9,1,100.00,,20.0,1,0,0",
    "2,200,2,1,1,1.00,,20.0,1,0,0",
]
UPC_ROWS = ["311,100,CEREAL ONE,10 OZ,12,1", "311,200,CEREAL TWO,15 OZ,12,2"]


def write_source(
    root: Path, movement_rows: list[str] | None = None, header: str = MOVEMENT_HEADER
) -> None:
    """Write movement, UPC, and week-decode files under root."""
    raw = root / "raw" / "cereal"
    raw.mkdir(parents=True, exist_ok=True)
    rows = MOVEMENT_ROWS if movement_rows is None else movement_rows
    (raw / "wcer.csv").write_text("\n".join([header, *rows]) + "\n")
    (raw / "upccer.csv").write_text(
        "\n".join(["COM_CODE,UPC,DESCRIP,SIZE,CASE,NITEM", *UPC_ROWS]) + "\n"
    )
    ref = root / "reference"
    ref.mkdir(exist_ok=True)
    shutil.copy(PROJECT_ROOT / "data" / "reference" / "week_decode.csv", ref / "week_decode.csv")
