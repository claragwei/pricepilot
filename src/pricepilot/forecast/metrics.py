"""Forecast accuracy metrics: WAPE, MAE, RMSE, bias, lift, and item-week aggregation."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

Array = NDArray[np.float64]
IntArray = NDArray[np.int64]


def wape(y: Array, pred: Array) -> float:
    """Weighted absolute percentage error: total absolute error over total actual units."""
    return float(np.abs(y - pred).sum() / y.sum())


def mae(y: Array, pred: Array) -> float:
    """Mean absolute error in units."""
    return float(np.abs(y - pred).mean())


def rmse(y: Array, pred: Array) -> float:
    """Root mean squared error in units."""
    return float(np.sqrt(np.mean((y - pred) ** 2)))


def bias(y: Array, pred: Array) -> float:
    """Total over- or under-forecast as a share of actual units (positive means over)."""
    return float((pred.sum() - y.sum()) / y.sum())


def lift(model_wape: float, baseline_wape: float) -> float:
    """Relative WAPE improvement over a baseline (positive means the model is better)."""
    return 1.0 - model_wape / baseline_wape


def item_week_totals(item: IntArray, week: IntArray, y: Array, pred: Array) -> tuple[Array, Array]:
    """Sum actual and predicted units over stores for each item and week."""
    keys = item * 1000 + week
    inverse = np.unique(keys, return_inverse=True)[1]
    return np.bincount(inverse, weights=y), np.bincount(inverse, weights=pred)


def score(y: Array, pred: Array, item: IntArray, week: IntArray) -> dict[str, float]:
    """All accuracy metrics at item-store-week level, plus WAPE at item-week level."""
    y_iw, pred_iw = item_week_totals(item, week, y, pred)
    return {
        "n": float(len(y)),
        "wape": wape(y, pred),
        "mae": mae(y, pred),
        "rmse": rmse(y, pred),
        "bias": bias(y, pred),
        "item_week_wape": wape(y_iw, pred_iw),
    }


def volume_deciles(volume: Array) -> IntArray:
    """Assign each row a volume decile from 0 (lowest) to 9 by recent mean units."""
    edges = np.quantile(volume, np.linspace(0.1, 0.9, 9))
    return np.digitize(volume, edges).astype(np.int64)


def group_wape(y: Array, pred: Array, groups: IntArray, n_groups: int) -> list[float | None]:
    """WAPE within each group, or None when a group is empty."""
    out: list[float | None] = []
    for g in range(n_groups):
        mask = groups == g
        out.append(wape(y[mask], pred[mask]) if mask.any() and y[mask].sum() > 0 else None)
    return out
