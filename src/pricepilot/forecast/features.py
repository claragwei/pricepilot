"""Feature stage: build the leakage-safe weekly feature matrix for one forecast horizon."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
from numpy.typing import NDArray

from pricepilot.config import PROJECT_ROOT, ForecastConfig

FEATURE_SQL = PROJECT_ROOT / "sql" / "features" / "weekly_features.sql"
CATEGORICAL_NAMES = ("item_code", "store_code")
NUMERIC_NAMES = (
    "lag_h",
    "lag_h1",
    "lag_h3",
    "lag_season",
    "mean4",
    "mean13",
    "price_t",
    "price_lag",
    "price_rel",
    "price_change",
    "promo_b",
    "promo_s",
    "promo_c",
    "promo_g",
    "promo_any",
    "promo_lag",
    "promo_share13",
    "margin_lag",
    "n_prior",
    "week_of_year",
    "month",
    "holiday_flag",
)
FEATURE_NAMES = (*CATEGORICAL_NAMES, *NUMERIC_NAMES)


@dataclass(frozen=True)
class FeatureSet:
    """Feature matrix for one horizon, with the target and the keys of each row."""

    horizon: int
    week: NDArray[np.int64]
    item: NDArray[np.int64]
    store: NDArray[np.int64]
    y: NDArray[np.float32]
    x: NDArray[np.float32]

    def column(self, name: str) -> NDArray[np.float32]:
        """Return one feature column by name."""
        return self.x[:, FEATURE_NAMES.index(name)]


def _as_float(column: Any) -> NDArray[np.float32]:
    """Convert a DuckDB numpy column to float32, turning nulls into NaN."""
    if np.ma.isMaskedArray(column):
        column = np.ma.filled(column.astype(np.float64), np.nan)
    return np.asarray(column, dtype=np.float32)


def build_features(
    con: duckdb.DuckDBPyConnection, cfg: ForecastConfig, input_dir: Path, horizon: int
) -> FeatureSet:
    """Build features for target weeks using only data observed at least `horizon` weeks earlier."""
    sql = FEATURE_SQL.read_text().format(
        horizon=horizon,
        horizon_p1=horizon + 1,
        horizon_p3=horizon + 3,
        horizon_p12=horizon + 12,
        season_lag=cfg.season_lag,
    )
    params = {
        "sales_path": str(input_dir / "fact_sales.parquet"),
        "prices_path": str(input_dir / "fact_prices.parquet"),
        "calendar_path": str(input_dir / "dim_calendar.parquet"),
    }
    con.execute(sql, params)
    cols = con.execute("select * from forecast_features").fetchnumpy()
    item = np.asarray(cols["item_id"], dtype=np.int64)
    store = np.asarray(cols["store_id"], dtype=np.int64)
    x = np.empty((len(item), len(FEATURE_NAMES)), dtype=np.float32)
    x[:, 0] = np.unique(item, return_inverse=True)[1]
    x[:, 1] = np.unique(store, return_inverse=True)[1]
    for j, name in enumerate(NUMERIC_NAMES, start=len(CATEGORICAL_NAMES)):
        x[:, j] = _as_float(cols[name])
    return FeatureSet(
        horizon=horizon,
        week=np.asarray(cols["week"], dtype=np.int64),
        item=item,
        store=store,
        y=_as_float(cols["y"]),
        x=x,
    )
