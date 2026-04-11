"""
Optuna-based optimization for NASABinner.

The objective prioritizes temporal separability while still considering IV and
temporal KS as supporting signals.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import numpy as np
import optuna
import pandas as pd

from .binning_engine import NASABinner
from .temporal_stability import (
    event_rate_by_time,
    ks_over_time,
    temporal_separability_score,
)

logger = logging.getLogger(__name__)


def _objective(
    trial: optuna.Trial,
    X: pd.DataFrame,
    y: pd.Series,
    base_kwargs: dict[str, Any],
    time_col: Optional[str],
    time_values: Optional[pd.Series],
    alpha: float,
    beta: float,
    gamma: float,
) -> float:
    """Objective function used by Optuna."""
    params = {
        "max_bins": trial.suggest_int("max_bins", 3, 10),
        "min_bin_size": trial.suggest_float("min_bin_size", 0.01, 0.1),
        "min_event_rate_diff": trial.suggest_float("min_event_rate_diff", 0.01, 0.1),
    }

    cfg = dict(base_kwargs)
    cfg.pop("min_event_rate_diff", None)
    cfg.pop("strategy_kwargs", None)

    binner = NASABinner(
        **cfg,
        max_bins=params["max_bins"],
        min_event_rate_diff=params["min_event_rate_diff"],
        strategy_kwargs={"min_bin_size": params["min_bin_size"]},
        use_optuna=False,
    )
    df_fit = X.copy()
    if time_col and time_values is not None:
        df_fit[time_col] = time_values

    binner.fit(df_fit, y, time_col=time_col)

    iv_value = binner.iv_
    n_bins = len(binner.bin_summary)

    if time_col and time_values is not None:
        bins = binner.transform(df_fit)[X.columns[0]]
        df_tmp = pd.DataFrame({"bin": bins, "target": y, "time": time_values})
        sep = temporal_separability_score(
            df_tmp,
            X.columns[0],
            "bin",
            "target",
            "time",
            penalize_inversions=True,
            penalize_low_freq=True,
            penalize_low_coverage=True,
        )
        tbl = (
            df_tmp.groupby(["bin", "time"])["target"]
            .agg(["sum", "count"])
            .reset_index()
            .rename(columns={"sum": "event"})
        )
        tbl["variable"] = X.columns[0]
        pivot = event_rate_by_time(tbl, "time")
        ks_value = ks_over_time(pivot)
    else:
        sep = 0.0
        ks_value = 0.0

    score = alpha * sep + beta * iv_value + gamma * ks_value
    if not np.isfinite(score):
        score = -1e6

    trial.set_user_attr("separability", sep)
    trial.set_user_attr("iv", iv_value)
    trial.set_user_attr("ks", ks_value)
    trial.set_user_attr("n_bins", n_bins)
    trial.set_user_attr("score", score)

    logger.info(
        "Trial %s: score=%.4f, sep=%.4f, iv=%.4f, ks=%.4f",
        trial.number,
        score,
        sep,
        iv_value,
        ks_value,
    )

    return float(score)


def optimize_bins(
    X: pd.DataFrame,
    y: pd.Series,
    *,
    time_col: str | None = None,
    time_values: Optional[pd.Series] = None,
    n_trials: int = 20,
    alpha: float = 0.7,
    beta: float = 0.2,
    gamma: float = 0.1,
    **base_kwargs,
) -> tuple[dict[str, Any], NASABinner]:
    """
    Execute Optuna and return the best parameters and fitted binner.
    """
    study = optuna.create_study(direction="maximize")
    optuna.logging.set_verbosity(optuna.logging.WARNING)

    study.optimize(
        lambda trial: _objective(
            trial,
            X,
            y,
            base_kwargs,
            time_col,
            time_values,
            alpha,
            beta,
            gamma,
        ),
        n_trials=n_trials,
        show_progress_bar=False,
    )

    if not study.best_trials:
        raise RuntimeError("Optuna nao concluiu nenhum trial valido.")

    best = study.best_trial
    best_params = {
        "max_bins": best.params["max_bins"],
        "min_bin_size": best.params["min_bin_size"],
        "min_event_rate_diff": best.params["min_event_rate_diff"],
    }

    cfg = dict(base_kwargs)
    cfg.pop("min_event_rate_diff", None)
    cfg.pop("strategy_kwargs", None)

    df_final = X.copy()
    if time_col and time_values is not None:
        df_final[time_col] = time_values

    final_binner = NASABinner(
        **cfg,
        max_bins=best_params["max_bins"],
        min_event_rate_diff=best_params["min_event_rate_diff"],
        strategy_kwargs={"min_bin_size": best_params["min_bin_size"]},
        use_optuna=False,
    ).fit(df_final, y, time_col=time_col)

    final_binner.best_params_ = best_params
    return best_params, final_binner
