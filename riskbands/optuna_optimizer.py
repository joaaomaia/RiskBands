"""
Optuna integration for RiskBands scoring objectives.

The scoring logic itself lives in ``riskbands.objectives`` so the same
objective can be reused with and without Optuna.
"""

from __future__ import annotations

from copy import deepcopy
import logging
from typing import Any, Optional

import numpy as np
import optuna
import pandas as pd

from .binning_engine import Binner
from .objectives import (
    DEFAULT_LEGACY_OBJECTIVE_CONFIG,
    build_objective_components,
    resolve_objective_config,
    score_objective_components,
)

logger = logging.getLogger(__name__)

DEFAULT_OBJECTIVE_CONFIG = deepcopy(DEFAULT_LEGACY_OBJECTIVE_CONFIG)


def _flatten_dict(prefix: str, value: Any, out: dict[str, Any]) -> None:
    if isinstance(value, dict):
        for key, inner in value.items():
            next_prefix = f"{prefix}_{key}" if prefix else key
            _flatten_dict(next_prefix, inner, out)
    else:
        out[prefix] = value


def _set_trial_objective_attrs(trial: optuna.Trial, objective_details: dict[str, Any]) -> None:
    flat = {}
    _flatten_dict("", objective_details, flat)
    for key, value in flat.items():
        if value is None:
            continue
        if isinstance(value, (np.generic,)):
            value = value.item()
        trial.set_user_attr(key, value)


def _objective(
    trial: optuna.Trial,
    X: pd.DataFrame,
    y: pd.Series,
    base_kwargs: dict[str, Any],
    time_col: Optional[str],
    time_values: Optional[pd.Series],
    objective_kwargs: dict[str, Any] | None,
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

    binner = Binner(
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
    components = build_objective_components(
        binner,
        df_fit,
        y,
        time_col=time_col,
        objective_kwargs=objective_kwargs,
    )
    objective_details = score_objective_components(components, objective_kwargs=objective_kwargs)

    _set_trial_objective_attrs(trial, objective_details)
    trial.set_user_attr("n_bins", len(binner.bin_summary))

    logger.info(
        "Trial %s: strategy=%s direction=%s score=%.4f penalty=%.4f",
        trial.number,
        objective_details.get("score_strategy"),
        objective_details.get("objective_direction"),
        objective_details["score"],
        objective_details["total_penalty"],
    )

    return float(objective_details["score"])


def optimize_bins(
    X: pd.DataFrame,
    y: pd.Series,
    *,
    time_col: str | None = None,
    time_values: Optional[pd.Series] = None,
    n_trials: int = 20,
    objective_kwargs: dict[str, Any] | None = None,
    **base_kwargs,
) -> tuple[dict[str, Any], Binner]:
    """
    Execute Optuna and return the best parameters and fitted binner.

    ``objective_kwargs`` is strategy-aware and can configure either the legacy
    score or ``stable`` without coupling the rest of the package to
    Optuna specifics.
    """
    resolved_objective_kwargs = resolve_objective_config(objective_kwargs)
    study = optuna.create_study(direction=resolved_objective_kwargs["objective_direction"])
    optuna.logging.set_verbosity(optuna.logging.WARNING)

    study.optimize(
        lambda trial: _objective(
            trial,
            X,
            y,
            base_kwargs,
            time_col,
            time_values,
            resolved_objective_kwargs,
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

    final_binner = Binner(
        **cfg,
        max_bins=best_params["max_bins"],
        min_event_rate_diff=best_params["min_event_rate_diff"],
        strategy_kwargs={"min_bin_size": best_params["min_bin_size"]},
        use_optuna=False,
    ).fit(df_final, y, time_col=time_col)

    components = build_objective_components(
        final_binner,
        df_final,
        y,
        time_col=time_col,
        objective_kwargs=resolved_objective_kwargs,
    )
    objective_summary = score_objective_components(
        components,
        objective_kwargs=resolved_objective_kwargs,
    )

    final_binner.best_params_ = best_params
    final_binner.objective_components_ = components
    final_binner.objective_summary_ = objective_summary
    final_binner.objective_config_ = resolved_objective_kwargs

    return best_params, final_binner
