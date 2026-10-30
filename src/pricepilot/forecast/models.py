"""Models: Poisson regression and LightGBM (Poisson objective) behind one fit-and-predict call."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import lightgbm as lgb
import numpy as np
from numpy.typing import NDArray
from sklearn.impute import SimpleImputer
from sklearn.linear_model import PoissonRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from pricepilot.config import GLMConfig, LightGBMConfig
from pricepilot.forecast.features import CATEGORICAL_NAMES

LOG_COLUMNS = frozenset(
    {
        "lag_h",
        "lag_h1",
        "lag_h3",
        "lag_season",
        "mean4",
        "mean13",
        "price_t",
        "price_lag",
        "price_rel",
    }
)


def glm_design(x: NDArray[np.float32], names: Sequence[str]) -> NDArray[np.float32]:
    """Drop id codes and log-transform unit and price columns for the linear model."""
    columns = []
    for j, name in enumerate(names):
        if name in CATEGORICAL_NAMES:
            continue
        column = x[:, j]
        columns.append(np.log1p(np.maximum(column, 0)) if name in LOG_COLUMNS else column)
    return np.column_stack(columns).astype(np.float32)


def fit_glm(
    x_train: NDArray[np.float32],
    y_train: NDArray[np.float32],
    names: Sequence[str],
    cfg: GLMConfig,
) -> Any:
    """Fit a Poisson regression on a capped random sample of training rows."""
    if len(y_train) > cfg.max_train_rows:
        rng = np.random.default_rng(cfg.seed)
        keep = np.sort(rng.choice(len(y_train), cfg.max_train_rows, replace=False))
        x_train, y_train = x_train[keep], y_train[keep]
    model = make_pipeline(
        SimpleImputer(strategy="median", add_indicator=True),
        StandardScaler(),
        PoissonRegressor(alpha=cfg.alpha, max_iter=cfg.max_iter),
    )
    model.fit(glm_design(x_train, names), y_train)
    return model


def predict_glm(model: Any, x: NDArray[np.float32], names: Sequence[str]) -> NDArray[np.float64]:
    """Predict units with a fitted Poisson regression."""
    return np.asarray(model.predict(glm_design(x, names)), dtype=np.float64)


def fit_lightgbm(
    x_train: NDArray[np.float32], y_train: NDArray[np.float32], cfg: LightGBMConfig
) -> Any:
    """Fit LightGBM with a Poisson objective, treating item and store codes as categorical."""
    model = lgb.LGBMRegressor(
        objective="poisson",
        n_estimators=cfg.n_estimators,
        learning_rate=cfg.learning_rate,
        num_leaves=cfg.num_leaves,
        min_child_samples=cfg.min_child_samples,
        colsample_bytree=cfg.feature_fraction,
        subsample=cfg.bagging_fraction,
        subsample_freq=1,
        random_state=cfg.seed,
        verbose=-1,
    )
    model.fit(x_train, y_train, categorical_feature=list(range(len(CATEGORICAL_NAMES))))
    return model


def predict_lightgbm(model: Any, x: NDArray[np.float32]) -> NDArray[np.float64]:
    """Predict units with a fitted LightGBM model."""
    return np.asarray(model.predict(x), dtype=np.float64)
