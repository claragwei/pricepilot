"""Baseline forecasters: seasonal-naive, last-week, and 4-week mean, with a recent-mean fallback."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from pricepilot.forecast.features import FeatureSet

BASELINES = ("seasonal_naive", "last_week", "mean4")


def evaluation_mask(fs: FeatureSet) -> NDArray[np.bool_]:
    """Rows with at least one observed week in the 13 weeks up to the forecast origin."""
    return ~np.isnan(fs.column("mean13"))


def baseline_predictions(fs: FeatureSet, rows: NDArray[np.bool_]) -> dict[str, NDArray[np.float64]]:
    """Predict the selected rows; a missing lag falls back to the 13-week mean."""
    fallback = fs.column("mean13")[rows].astype(np.float64)
    sources = {
        "seasonal_naive": "lag_season",
        "last_week": "lag_h",
        "mean4": "mean4",
    }
    out: dict[str, NDArray[np.float64]] = {}
    for name, column in sources.items():
        primary = fs.column(column)[rows].astype(np.float64)
        out[name] = np.where(np.isnan(primary), fallback, primary)
    return out
