"""Integration tests for the feature SQL and the backtest on a small synthetic panel."""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from pathlib import Path

import duckdb
import numpy as np
import pytest

from pricepilot.config import FoldConfig, ForecastConfig, load_forecast_config
from pricepilot.forecast.backtest import MODEL_NAMES, run_backtest
from pricepilot.forecast.features import FEATURE_NAMES, build_features
from pricepilot.forecast.run import run

WEEKS = range(1, 71)


def _units(item: int, week: int) -> int:
    """Deterministic units: a trend, an item offset, and a weekly pattern."""
    return 10 + item * 3 + week // 5 + week % 7


def write_inputs(
    root: Path, units: Callable[[int, int], int] = _units, skip: set[tuple[int, int]] | None = None
) -> None:
    """Write fact_sales, fact_prices, and dim_calendar Parquet files for a tiny panel."""
    skip = skip or set()
    con = duckdb.connect()
    con.execute("create table s (item_id bigint, store_id int, WEEK int, units_sold int)")
    con.execute(
        "create table p (item_id bigint, store_id int, WEEK int, sell_price double, "
        "promo_code varchar, gross_margin_pct double)"
    )
    for item in (1, 2, 3):
        for store in (1, 2):
            for week in WEEKS:
                if (item, week) in skip:
                    continue
                con.execute(
                    "insert into s values (?, ?, ?, ?)", [item, store, week, units(item, week)]
                )
                code = "B" if week % 10 == 0 else None
                price = 2.0 + 0.01 * week + store * 0.1
                con.execute(
                    "insert into p values (?, ?, ?, ?, ?, 25.0)", [item, store, week, price, code]
                )
    con.execute("create table c (week int, week_start date, holiday_flag int)")
    start = dt.date(1989, 9, 14)
    for week in WEEKS:
        con.execute(
            "insert into c values (?, ?, 0)", [week, start + dt.timedelta(days=7 * (week - 1))]
        )
    root.mkdir(parents=True, exist_ok=True)
    for table, name in (("s", "fact_sales"), ("p", "fact_prices"), ("c", "dim_calendar")):
        con.execute(f"copy {table} to '{root / name}.parquet' (format parquet)")
    con.close()


def _row(fs_week: np.ndarray, fs_item: np.ndarray, fs_store: np.ndarray, week: int) -> int:
    """Index of the row for item 1, store 1 in a given week."""
    return int(np.flatnonzero((fs_week == week) & (fs_item == 1) & (fs_store == 1))[0])


def test_lag_and_window_features(tmp_path: Path) -> None:
    """Lags and windows reference the right weeks for a given horizon."""
    write_inputs(tmp_path)
    cfg = load_forecast_config()
    fs = build_features(duckdb.connect(), cfg, tmp_path, horizon=2)
    i = _row(fs.week, fs.item, fs.store, 60)
    assert fs.y[i] == _units(1, 60)
    assert fs.column("lag_h")[i] == _units(1, 58)
    assert fs.column("lag_h1")[i] == _units(1, 57)
    assert fs.column("lag_h3")[i] == _units(1, 55)
    assert fs.column("lag_season")[i] == _units(1, 8)
    assert fs.column("mean4")[i] == pytest.approx(np.mean([_units(1, w) for w in range(55, 59)]))
    assert fs.column("price_t")[i] == pytest.approx(2.0 + 0.6 + 0.1)
    assert fs.column("promo_b")[i] == 1.0
    assert fs.column("n_prior")[i] == 58.0


def test_missing_week_becomes_nan(tmp_path: Path) -> None:
    """A missing observation yields NaN lags instead of shifting to an earlier row."""
    write_inputs(tmp_path, skip={(1, 28)})
    cfg = load_forecast_config()
    fs = build_features(duckdb.connect(), cfg, tmp_path, horizon=2)
    i = _row(fs.week, fs.item, fs.store, 30)
    assert np.isnan(fs.column("lag_h")[i])
    assert fs.column("lag_h1")[i] == _units(1, 27)
    assert fs.column("mean4")[i] == pytest.approx(np.mean([_units(1, w) for w in (25, 26, 27)]))


def test_features_do_not_use_future_units(tmp_path: Path) -> None:
    """Changing units from week 60 on leaves features of rows up to week 61 unchanged."""
    cfg = load_forecast_config()
    base = tmp_path / "base"
    changed = tmp_path / "changed"
    write_inputs(base)
    write_inputs(changed, units=lambda item, week: _units(item, week) + (1000 if week >= 60 else 0))
    a = build_features(duckdb.connect(), cfg, base, horizon=2)
    b = build_features(duckdb.connect(), cfg, changed, horizon=2)
    early = a.week <= 61
    assert np.array_equal(a.x[early], b.x[early], equal_nan=True)
    assert not np.array_equal(a.x[~early], b.x[~early], equal_nan=True)


def _small_cfg() -> ForecastConfig:
    """The project config reduced to a single horizon and tiny models."""
    base = load_forecast_config()
    return base.model_copy(
        update={
            "horizons": [2],
            "lightgbm": base.lightgbm.model_copy(
                update={"n_estimators": 5, "min_child_samples": 5}
            ),
            "glm": base.glm.model_copy(update={"max_iter": 50}),
        }
    )


def test_backtest_runs_end_to_end(tmp_path: Path) -> None:
    """Every model is scored on every fold and the training window respects the horizon."""
    write_inputs(tmp_path)
    folds = [
        FoldConfig(train_end=40, test_start=41, test_end=50),
        FoldConfig(train_end=50, test_start=51, test_end=60),
    ]
    results = run_backtest(duckdb.connect(), _small_cfg(), tmp_path, folds)
    horizon = results["horizons"]["2"]
    assert [f["train_end"] for f in horizon["per_fold"]] == [39, 49]
    pooled = horizon["pooled"]["models"]
    assert set(pooled) == set(MODEL_NAMES)
    assert all(0 <= s["wape"] < 5 for s in pooled.values())
    assert pooled["seasonal_naive"]["lift_vs_seasonal_naive"] == pytest.approx(0.0)
    assert len(horizon["segments"]["lightgbm"]["volume_decile_wape"]) == 10
    assert len(FEATURE_NAMES) == 24


def test_final_test_is_run_once(tmp_path: Path) -> None:
    """A second final run is refused unless explicitly requested."""
    out = tmp_path / "out"
    out.mkdir()
    (out / "final_metrics.json").write_text("{}")
    with pytest.raises(FileExistsError):
        run(_small_cfg(), tmp_path, out, final=True)
