"""
Credit-oriented Optuna objective for RiskBands.

The optimizer remains focused on the RiskBands core: selecting binnings that
balance static discrimination with temporal stability, structural robustness,
and interpretability signals that matter in PD workflows.
"""

from __future__ import annotations

from copy import deepcopy
import logging
from typing import Any, Optional

import numpy as np
import optuna
import pandas as pd

from .binning_engine import Binner
from .temporal_stability import event_rate_by_time, ks_over_time, temporal_separability_score

logger = logging.getLogger(__name__)


DEFAULT_OBJECTIVE_CONFIG = {
    "base_weights": {
        "separability": 0.35,
        "iv": 0.35,
        "ks": 0.10,
        "temporal_score": 0.20,
    },
    "penalty_weights": {
        "rare_bin_count": 0.03,
        "coverage_gap": 0.20,
        "event_rate_volatility": 0.30,
        "woe_volatility": 0.08,
        "share_volatility": 0.20,
        "monotonic_breaks": 0.03,
        "ranking_reversals": 0.05,
        "iv_shortfall": 0.80,
        "temporal_shortfall": 0.50,
    },
    "minimums": {
        "iv": 0.02,
        "temporal_score": 0.02,
        "coverage_ratio": 0.60,
    },
    "diagnostics": {
        "dataset_name": "optimization",
        "min_bin_count": 30,
        "min_bin_share": 0.05,
        "min_time_coverage": 0.75,
    },
}


def _deep_update(target: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    for key, value in source.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_update(target[key], value)
        else:
            target[key] = value
    return target


def resolve_objective_config(objective_kwargs: dict[str, Any] | None = None) -> dict[str, Any]:
    config = deepcopy(DEFAULT_OBJECTIVE_CONFIG)
    if objective_kwargs:
        _deep_update(config, objective_kwargs)
    return config


def _safe_float(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        value = float(value)
    except (TypeError, ValueError):
        return 0.0
    if not np.isfinite(value):
        return 0.0
    return float(value)


def build_objective_components(
    binner: Binner,
    X: pd.DataFrame,
    y: pd.Series,
    *,
    time_col: str | None = None,
    objective_kwargs: dict[str, Any] | None = None,
) -> dict[str, float]:
    """
    Build the scalar components used by the credit-oriented objective.

    When temporal information is available, this function explicitly reuses the
    diagnostics layer added in Sprint 2.
    """
    config = resolve_objective_config(objective_kwargs)
    diagnostics_cfg = config["diagnostics"]
    components = {
        "iv": _safe_float(getattr(binner, "iv_", 0.0)),
        "separability": 0.0,
        "ks": 0.0,
        "temporal_score": 0.0,
        "n_bins_effective": 0.0,
        "coverage_ratio_min": 1.0,
        "coverage_ratio_mean": 1.0,
        "rare_bin_count": 0.0,
        "event_rate_std_mean": 0.0,
        "event_rate_std_max": 0.0,
        "woe_std_mean": 0.0,
        "woe_std_max": 0.0,
        "bin_share_std_mean": 0.0,
        "bin_share_std_max": 0.0,
        "monotonic_break_period_count": 0.0,
        "ranking_reversal_period_count": 0.0,
        "bins_missing_any_period_count": 0.0,
        "missing_period_count": 0.0,
        "low_coverage_bin_count": 0.0,
    }

    if not time_col or time_col not in X.columns:
        return components

    diagnostics = binner.temporal_bin_diagnostics(
        X,
        y,
        time_col=time_col,
        dataset_name=diagnostics_cfg["dataset_name"],
        min_bin_count=diagnostics_cfg["min_bin_count"],
        min_bin_share=diagnostics_cfg["min_bin_share"],
        min_time_coverage=diagnostics_cfg["min_time_coverage"],
    )
    summary = binner.temporal_variable_summary(diagnostics=diagnostics, time_col=time_col)

    if not summary.empty:
        row = summary.iloc[0]
        for column in (
            "temporal_score",
            "n_bins_effective",
            "coverage_ratio_min",
            "coverage_ratio_mean",
            "rare_bin_count",
            "event_rate_std_mean",
            "event_rate_std_max",
            "woe_std_mean",
            "woe_std_max",
            "bin_share_std_mean",
            "bin_share_std_max",
            "monotonic_break_period_count",
            "ranking_reversal_period_count",
            "bins_missing_any_period_count",
            "missing_period_count",
            "low_coverage_bin_count",
        ):
            components[column] = _safe_float(row.get(column, 0.0))

    variable = binner.bin_summary["variable"].iloc[0]
    bins = binner.transform(X)[variable]
    df_tmp = pd.DataFrame({"bin": bins, "target": y, "time": X[time_col]})

    components["separability"] = _safe_float(
        temporal_separability_score(
            df_tmp,
            variable,
            "bin",
            "target",
            "time",
            penalize_inversions=False,
            penalize_low_freq=False,
            penalize_low_coverage=False,
        )
    )

    tbl = (
        df_tmp.groupby(["bin", "time"])["target"]
        .agg(["sum", "count"])
        .reset_index()
        .rename(columns={"sum": "event"})
    )
    tbl["variable"] = variable
    components["ks"] = _safe_float(ks_over_time(event_rate_by_time(tbl, "time")))
    return components


def score_objective_components(
    components: dict[str, Any],
    *,
    objective_kwargs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Combine discrimination and temporal diagnostics into a single score.

    The final score follows a simple philosophy suitable for credit-oriented
    binning:
    - reward viable separation and stability
    - penalize unstable, rare, or structurally fragile bins
    - softly penalize candidates below minimum discrimination/stability floors
    """
    config = resolve_objective_config(objective_kwargs)
    base_weights = config["base_weights"]
    penalty_weights = config["penalty_weights"]
    minimums = config["minimums"]

    comps = {key: _safe_float(value) for key, value in components.items()}

    base_components = {
        "separability_component": base_weights["separability"] * max(comps.get("separability", 0.0), 0.0),
        "iv_component": base_weights["iv"] * max(comps.get("iv", 0.0), 0.0),
        "ks_component": base_weights["ks"] * max(comps.get("ks", 0.0), 0.0),
        "temporal_score_component": base_weights["temporal_score"]
        * max(comps.get("temporal_score", 0.0), 0.0),
    }

    penalties = {
        "rare_bin_penalty": penalty_weights["rare_bin_count"] * max(comps.get("rare_bin_count", 0.0), 0.0),
        "coverage_gap_penalty": penalty_weights["coverage_gap"]
        * max(0.0, minimums["coverage_ratio"] - comps.get("coverage_ratio_min", 1.0)),
        "event_rate_volatility_penalty": penalty_weights["event_rate_volatility"]
        * max(comps.get("event_rate_std_max", 0.0), 0.0),
        "woe_volatility_penalty": penalty_weights["woe_volatility"]
        * max(comps.get("woe_std_max", 0.0), 0.0),
        "share_volatility_penalty": penalty_weights["share_volatility"]
        * max(comps.get("bin_share_std_max", 0.0), 0.0),
        "monotonic_break_penalty": penalty_weights["monotonic_breaks"]
        * max(comps.get("monotonic_break_period_count", 0.0), 0.0),
        "ranking_reversal_penalty": penalty_weights["ranking_reversals"]
        * max(comps.get("ranking_reversal_period_count", 0.0), 0.0),
        "iv_shortfall_penalty": penalty_weights["iv_shortfall"]
        * max(0.0, minimums["iv"] - comps.get("iv", 0.0)),
        "temporal_shortfall_penalty": penalty_weights["temporal_shortfall"]
        * max(0.0, minimums["temporal_score"] - comps.get("temporal_score", 0.0)),
    }

    base_score = float(sum(base_components.values()))
    total_penalty = float(sum(penalties.values()))
    score = base_score - total_penalty
    if not np.isfinite(score):
        score = -1e6

    minimum_checks = {
        "meets_iv_floor": comps.get("iv", 0.0) >= minimums["iv"],
        "meets_temporal_floor": comps.get("temporal_score", 0.0) >= minimums["temporal_score"],
        "meets_coverage_floor": comps.get("coverage_ratio_min", 1.0) >= minimums["coverage_ratio"],
    }

    return {
        "score": float(score),
        "base_score": base_score,
        "total_penalty": total_penalty,
        "components": comps,
        "base_components": base_components,
        "penalties": penalties,
        "minimum_checks": minimum_checks,
        "objective_config": config,
    }


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
        "Trial %s: score=%.4f, base=%.4f, penalty=%.4f, iv=%.4f, temporal=%.4f",
        trial.number,
        objective_details["score"],
        objective_details["base_score"],
        objective_details["total_penalty"],
        components.get("iv", 0.0),
        components.get("temporal_score", 0.0),
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

    ``objective_kwargs`` allows light customization of the credit-oriented
    objective without turning the API into a broad risk framework.
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
            objective_kwargs,
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
        objective_kwargs=objective_kwargs,
    )
    objective_summary = score_objective_components(components, objective_kwargs=objective_kwargs)

    final_binner.best_params_ = best_params
    final_binner.objective_components_ = components
    final_binner.objective_summary_ = objective_summary
    final_binner.objective_config_ = resolve_objective_config(objective_kwargs)

    return best_params, final_binner


