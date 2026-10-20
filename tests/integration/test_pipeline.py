"""End-to-end tests of the data pipeline on a tiny fixture dataset."""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest
from tests.helpers import MOVEMENT_HEADER, MOVEMENT_ROWS, write_source

from pricepilot.config import DataConfig
from pricepilot.data.ingest import IngestError
from pricepilot.data.pipeline import PipelineError, run


def query(path: Path, sql: str) -> list[tuple]:
    """Run SQL against a Parquet file referenced as {t}."""
    return duckdb.sql(sql.format(t=f"read_parquet('{path}')")).fetchall()


def test_row_status_counts(root: Path, cfg: DataConfig) -> None:
    result = run(cfg, root)
    assert result.row_counts["fact_sales"] == 5
    assert result.row_counts["fact_prices"] == 5
    assert result.report.stats["row_status"] == {
        "accepted": 5,
        "flagged_not_ok": 1,
        "invalid_value": 1,
        "implausible_price": 1,
        "no_sale_recorded": 1,
    }
    assert not result.report.failed_required()


def test_bundle_price_cost_and_dates(root: Path, cfg: DataConfig) -> None:
    out = run(cfg, root).output_dir / "fact_prices.parquet"
    rows = {
        r[0]: r
        for r in query(
            out,
            "select week, week_start, sell_price, unit_cost, promo_code from {t} "
            "where store_id = 1 and item_id = 100",
        )
    }
    assert str(rows[1][1]) == "1989-09-14"
    assert rows[1][2] == pytest.approx(2.0) and rows[1][3] == pytest.approx(1.5)
    assert rows[2][2] == pytest.approx(1.0) and rows[2][3] == pytest.approx(0.7)
    assert rows[2][4] == "B"
    assert rows[6][3] is None
    assert rows[7][3] == pytest.approx(2.2)


def test_rerun_is_idempotent(root: Path, cfg: DataConfig) -> None:
    first = run(cfg, root)
    snapshot = {
        t: query(first.output_dir / f"{t}.parquet", "select * from {t} order by all")
        for t in ("fact_sales", "fact_prices", "dim_product", "dim_calendar")
    }
    second = run(cfg, root)
    for t, rows in snapshot.items():
        assert query(second.output_dir / f"{t}.parquet", "select * from {t} order by all") == rows
    log = (second.output_dir / "run_log.jsonl").read_text().splitlines()
    assert len(log) == 2 and json.loads(log[-1])["status"] == "success"


def test_sample_run_filters_and_isolates_output(root: Path, cfg: DataConfig) -> None:
    result = run(cfg, root, sample=True)
    assert result.output_dir.name == "cereal_sample"
    assert result.row_counts["fact_sales"] == 2
    assert not (root / "processed" / "cereal").exists()


def test_missing_file_gives_actionable_error(tmp_path: Path, cfg: DataConfig) -> None:
    with pytest.raises(IngestError, match="wcer.csv"):
        run(cfg, tmp_path)


def test_missing_column_fails(tmp_path: Path, cfg: DataConfig) -> None:
    write_source(tmp_path, header=MOVEMENT_HEADER.replace("PRICE,", "COST,"))
    with pytest.raises(IngestError, match="PRICE"):
        run(cfg, tmp_path)


def test_bad_value_type_fails(tmp_path: Path, cfg: DataConfig) -> None:
    write_source(tmp_path, ["1,100,1,five,1,2.00,,25.0,1,0,0"])
    with pytest.raises(IngestError):
        run(cfg, tmp_path)


@pytest.mark.parametrize(
    ("extra_row", "failed_check"),
    [
        ("1,100,1,7,1,2.50,,20.0,1,0,0", "movement_grain_unique"),
        ("3,100,999,7,1,2.50,,20.0,1,0,0", "weeks_in_calendar"),
        ("3,999,1,7,1,2.50,,20.0,1,0,0", "upcs_in_product_dim"),
    ],
)
def test_bad_input_blocks_load_but_writes_report(
    tmp_path: Path, cfg: DataConfig, extra_row: str, failed_check: str
) -> None:
    write_source(tmp_path, [*MOVEMENT_ROWS, extra_row])
    with pytest.raises(PipelineError, match=failed_check):
        run(cfg, tmp_path)
    out = tmp_path / "processed" / "cereal"
    assert not list(out.glob("*.parquet"))
    report = json.loads((out / "quality_report.json").read_text())
    assert failed_check in {c["name"] for c in report["checks"] if not c["passed"]}


def test_reject_rate_limit_fails(root: Path, cfg: DataConfig) -> None:
    strict = cfg.model_copy(update={"max_reject_rate": 0.1})
    with pytest.raises(PipelineError, match="reject_rate_within_limit"):
        run(strict, root)
