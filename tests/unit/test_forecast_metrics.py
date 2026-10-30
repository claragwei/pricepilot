"""Unit tests for forecast metrics, baselines, and fold validation."""

from __future__ import annotations

import numpy as np
import pytest

from pricepilot.config import FoldConfig, load_forecast_config
from pricepilot.forecast import baselines, metrics
from pricepilot.forecast.backtest import effective_train_end, validate_folds
from pricepilot.forecast.features import FEATURE_NAMES, FeatureSet


def test_wape_bias_rmse_mae() -> None:
    """Basic metrics match hand-computed values."""
    y = np.array([10.0, 10.0])
    pred = np.array([8.0, 12.0])
    assert metrics.wape(y, pred) == pytest.approx(0.2)
    assert metrics.bias(y, pred) == pytest.approx(0.0)
    assert metrics.bias(y, np.array([12.0, 12.0])) == pytest.approx(0.2)
    assert metrics.mae(y, pred) == pytest.approx(2.0)
    assert metrics.rmse(y, pred) == pytest.approx(2.0)


def test_lift_is_relative_improvement() -> None:
    """Lift is positive when the model beats the baseline."""
    assert metrics.lift(0.8, 1.0) == pytest.approx(0.2)
    assert metrics.lift(1.2, 1.0) == pytest.approx(-0.2)


def test_item_week_totals_sum_over_stores() -> None:
    """Item-week aggregation lets store-level errors cancel."""
    item = np.array([7, 7, 8], dtype=np.int64)
    week = np.array([1, 1, 1], dtype=np.int64)
    y = np.array([5.0, 5.0, 4.0])
    pred = np.array([6.0, 4.0, 4.0])
    y_iw, pred_iw = metrics.item_week_totals(item, week, y, pred)
    assert sorted(y_iw) == [4.0, 10.0]
    result = metrics.score(y, pred, item, week)
    assert result["wape"] == pytest.approx(2 / 14)
    assert result["item_week_wape"] == pytest.approx(0.0)


def test_group_wape_none_for_empty_group() -> None:
    """A group with no rows reports None instead of failing."""
    y = np.array([10.0, 10.0])
    pred = np.array([9.0, 9.0])
    groups = np.array([0, 0], dtype=np.int64)
    assert metrics.group_wape(y, pred, groups, 2) == [pytest.approx(0.1), None]


def test_volume_deciles_span_zero_to_nine() -> None:
    """Deciles cover 0 through 9 on evenly spread volumes."""
    deciles = metrics.volume_deciles(np.arange(1000, dtype=np.float64))
    assert deciles.min() == 0
    assert deciles.max() == 9


def _feature_set(rows: list[dict[str, float]]) -> FeatureSet:
    """Build a FeatureSet whose unspecified features are NaN."""
    x = np.full((len(rows), len(FEATURE_NAMES)), np.nan, dtype=np.float32)
    for i, row in enumerate(rows):
        for name, value in row.items():
            x[i, FEATURE_NAMES.index(name)] = value
    n = len(rows)
    return FeatureSet(
        horizon=1,
        week=np.arange(n, dtype=np.int64),
        item=np.zeros(n, dtype=np.int64),
        store=np.zeros(n, dtype=np.int64),
        y=np.ones(n, dtype=np.float32),
        x=x,
    )


def test_baselines_fall_back_to_recent_mean() -> None:
    """Missing lags use the 13-week mean, and rows without history are not scored."""
    fs = _feature_set(
        [
            {"lag_season": 5, "lag_h": 7, "mean4": 6, "mean13": 4},
            {"mean13": 4},
            {},
        ]
    )
    mask = baselines.evaluation_mask(fs)
    assert mask.tolist() == [True, True, False]
    preds = baselines.baseline_predictions(fs, mask)
    assert preds["seasonal_naive"].tolist() == [5.0, 4.0]
    assert preds["last_week"].tolist() == [7.0, 4.0]
    assert preds["mean4"].tolist() == [6.0, 4.0]


def test_effective_train_end_respects_horizon() -> None:
    """Training labels must be known at the first test week's forecast origin."""
    fold = FoldConfig(train_end=100, test_start=101, test_end=110)
    assert effective_train_end(fold, 1) == 100
    assert effective_train_end(fold, 4) == 97


def test_validate_folds_rejects_bad_windows() -> None:
    """Overlapping or inverted windows are rejected."""
    good = FoldConfig(train_end=10, test_start=11, test_end=15)
    validate_folds([good, FoldConfig(train_end=15, test_start=16, test_end=20)])
    with pytest.raises(ValueError, match="train_end < test_start"):
        validate_folds([FoldConfig(train_end=12, test_start=11, test_end=15)])
    with pytest.raises(ValueError, match="overlaps"):
        validate_folds([good, FoldConfig(train_end=12, test_start=14, test_end=20)])


def test_project_folds_are_valid() -> None:
    """The configured validation folds and the final test are ordered and disjoint."""
    cfg = load_forecast_config()
    validate_folds([*cfg.folds, cfg.final_test])
