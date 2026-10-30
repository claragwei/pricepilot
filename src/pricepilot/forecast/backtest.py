"""Rolling-origin backtest: fold validation, per-fold scoring, and pooled segment metrics."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
from numpy.typing import NDArray

from pricepilot.config import FoldConfig, ForecastConfig
from pricepilot.forecast import baselines, metrics, models
from pricepilot.forecast.features import FEATURE_NAMES, FeatureSet, build_features

MODEL_NAMES = (*baselines.BASELINES, "poisson_glm", "lightgbm")
REFERENCE_MODEL = "seasonal_naive"


def validate_folds(folds: Sequence[FoldConfig]) -> None:
    """Require training to end before testing starts and test windows to be ordered and disjoint."""
    previous_end = 0
    for number, fold in enumerate(folds, start=1):
        if not fold.train_end < fold.test_start <= fold.test_end:
            raise ValueError(f"fold {number}: need train_end < test_start <= test_end")
        if fold.test_start <= previous_end:
            raise ValueError(f"fold {number}: test window overlaps the previous fold")
        previous_end = fold.test_end


def effective_train_end(fold: FoldConfig, horizon: int) -> int:
    """Last target week whose label is known at the forecast origin of the first test week."""
    return min(fold.train_end, fold.test_start - horizon)


def predict_fold(
    fs: FeatureSet,
    fold: FoldConfig,
    cfg: ForecastConfig,
) -> tuple[NDArray[np.bool_], dict[str, NDArray[np.float64]]]:
    """Train on labels known before the fold and predict every scored row in its test window."""
    train = fs.week <= effective_train_end(fold, fs.horizon)
    in_window = (fs.week >= fold.test_start) & (fs.week <= fold.test_end)
    test = in_window & baselines.evaluation_mask(fs)
    if not train.any() or not test.any():
        raise ValueError(f"fold {fold} has no training or no scored rows")
    preds = baselines.baseline_predictions(fs, test)
    x_train, y_train, x_test = fs.x[train], fs.y[train], fs.x[test]
    glm = models.fit_glm(x_train, y_train, FEATURE_NAMES, cfg.glm)
    gbm = models.fit_lightgbm(x_train, y_train, cfg.lightgbm)
    preds["poisson_glm"] = models.predict_glm(glm, x_test, FEATURE_NAMES)
    preds["lightgbm"] = models.predict_lightgbm(gbm, x_test)
    return test, preds


def run_horizon(
    fs: FeatureSet,
    folds: Sequence[FoldConfig],
    cfg: ForecastConfig,
) -> dict[str, Any]:
    """Score every model on every fold for one horizon, then pool folds for segment metrics."""
    per_fold: list[dict[str, Any]] = []
    pool: dict[str, list[NDArray[Any]]] = {"y": [], "item": [], "week": [], "promo": [], "vol": []}
    pooled_preds: dict[str, list[NDArray[np.float64]]] = {name: [] for name in MODEL_NAMES}
    for number, fold in enumerate(folds, start=1):
        test, preds = predict_fold(fs, fold, cfg)
        y = fs.y[test].astype(np.float64)
        item, week = fs.item[test], fs.week[test]
        per_fold.append(
            {
                "fold": number,
                "train_end": effective_train_end(fold, fs.horizon),
                "test_start": fold.test_start,
                "test_end": fold.test_end,
                "n_test": int(test.sum()),
                "models": {name: metrics.score(y, p, item, week) for name, p in preds.items()},
            }
        )
        pool["y"].append(y)
        pool["item"].append(item)
        pool["week"].append(week)
        pool["promo"].append(fs.column("promo_any")[test])
        pool["vol"].append(fs.column("mean13")[test])
        for name, p in preds.items():
            pooled_preds[name].append(p)
    y_all = np.concatenate(pool["y"])
    item_all, week_all = np.concatenate(pool["item"]), np.concatenate(pool["week"])
    promo_all = (np.concatenate(pool["promo"]) > 0).astype(np.int64)
    deciles = metrics.volume_deciles(np.concatenate(pool["vol"]).astype(np.float64))
    pooled: dict[str, dict[str, float]] = {}
    segments: dict[str, dict[str, list[float | None]]] = {}
    for name in MODEL_NAMES:
        p_all = np.concatenate(pooled_preds[name])
        pooled[name] = metrics.score(y_all, p_all, item_all, week_all)
        segments[name] = {
            "promo_wape": metrics.group_wape(y_all, p_all, promo_all, 2),
            "volume_decile_wape": metrics.group_wape(y_all, p_all, deciles, 10),
        }
    reference = pooled[REFERENCE_MODEL]["wape"]
    for scores in pooled.values():
        scores["lift_vs_seasonal_naive"] = metrics.lift(scores["wape"], reference)
    return {
        "horizon": fs.horizon,
        "per_fold": per_fold,
        "pooled": {"n": int(len(y_all)), "models": pooled},
        "segments": segments,
    }


def run_backtest(
    con: duckdb.DuckDBPyConnection,
    cfg: ForecastConfig,
    input_dir: Path,
    folds: Sequence[FoldConfig],
) -> dict[str, Any]:
    """Run the backtest for every configured horizon over the given folds."""
    validate_folds(folds)
    horizons: dict[str, Any] = {}
    for horizon in cfg.horizons:
        fs = build_features(con, cfg, input_dir, horizon)
        horizons[str(horizon)] = run_horizon(fs, folds, cfg)
    return {"folds": [fold.model_dump() for fold in folds], "horizons": horizons}
