"""Objective scoring strategies for RiskBands."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from .temporal_stability import event_rate_by_time, ks_over_time, temporal_separability_score

EPSILON = 1e-9

LEGACY_SCORE_STRATEGY = "legacy"
STABLE_SCORE_STRATEGY = "stable"
DEFAULT_SCORE_STRATEGY = LEGACY_SCORE_STRATEGY

STABLE_COMPONENT_TO_WEIGHT = {
    "temporal_variance": "temporal_variance_weight",
    "window_drift": "window_drift_weight",
    "rank_inversion": "rank_inversion_weight",
    "separation": "separation_weight",
    "entropy": "entropy_weight",
    "psi": "psi_weight",
}

STABLE_WEIGHT_ALIASES = {
    "temporal_variance": "temporal_variance_weight",
    "window_drift": "window_drift_weight",
    "rank_inversion": "rank_inversion_weight",
    "separation": "separation_weight",
    "entropy": "entropy_weight",
    "psi": "psi_weight",
}


DEFAULT_LEGACY_OBJECTIVE_CONFIG = {
    "score_strategy": LEGACY_SCORE_STRATEGY,
    "objective_direction": "maximize",
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


@dataclass(frozen=True)
class TemporalDiagnosticsConfig:
    dataset_name: str = "optimization"
    min_bin_count: int = 30
    min_bin_share: float = 0.05
    min_time_coverage: float = 0.75


@dataclass(frozen=True)
class StableScoreWeights:
    temporal_variance_weight: float = 0.22
    window_drift_weight: float = 0.18
    rank_inversion_weight: float = 0.20
    separation_weight: float = 0.20
    entropy_weight: float = 0.08
    psi_weight: float = 0.12


@dataclass(frozen=True)
class StableNormalizationConfig:
    temporal_variance_scale: float = 0.0625
    window_drift_scale: float = 0.25
    separation_scale: float = 0.10
    psi_scale: float = 0.10


@dataclass(frozen=True)
class StableObjectiveConfig:
    score_strategy: str = STABLE_SCORE_STRATEGY
    objective_direction: str = "minimize"
    weights: StableScoreWeights = field(default_factory=StableScoreWeights)
    normalization_strategy: str = "absolute"
    normalization: StableNormalizationConfig = field(
        default_factory=StableNormalizationConfig
    )
    woe_shrinkage_strength: float = 25.0
    diagnostics: TemporalDiagnosticsConfig = field(default_factory=TemporalDiagnosticsConfig)


def _deep_update(target: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    for key, value in source.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_update(target[key], value)
        else:
            target[key] = value
    return target


def _safe_float(value: Any, *, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        value = float(value)
    except (TypeError, ValueError):
        return default
    if not np.isfinite(value):
        return default
    return float(value)


def _clip_ratio(values: np.ndarray) -> np.ndarray:
    return np.clip(values.astype(float), EPSILON, None)


def _bounded_normalize(value: float, *, lower: float = 0.0, upper: float = 1.0) -> float:
    if upper <= lower:
        raise ValueError("upper must be greater than lower for bounded normalization.")
    value = _safe_float(value)
    if value <= lower:
        return 0.0
    if value >= upper:
        return 1.0
    return float((value - lower) / (upper - lower))


def _saturating_normalize(value: float, *, scale: float) -> float:
    value = max(_safe_float(value), 0.0)
    scale = max(_safe_float(scale, default=0.0), EPSILON)
    return float(value / (value + scale))


def _weighted_mean(values: np.ndarray, weights: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    weights = np.asarray(weights, dtype=float)
    mask = np.isfinite(values) & np.isfinite(weights) & (weights > 0)
    if not mask.any():
        return 0.0
    return float(np.average(values[mask], weights=weights[mask]))


def _weighted_variance(values: np.ndarray, weights: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    weights = np.asarray(weights, dtype=float)
    mask = np.isfinite(values) & np.isfinite(weights) & (weights > 0)
    if mask.sum() <= 1:
        return 0.0
    mean = np.average(values[mask], weights=weights[mask])
    variance = np.average((values[mask] - mean) ** 2, weights=weights[mask])
    return float(max(variance, 0.0))


def _psi_from_arrays(expected: np.ndarray, actual: np.ndarray) -> float:
    expected = _clip_ratio(np.asarray(expected, dtype=float))
    actual = _clip_ratio(np.asarray(actual, dtype=float))
    return float(np.sum((actual - expected) * np.log(actual / expected)))


def resolve_score_strategy(
    objective_kwargs: dict[str, Any] | None = None,
    *,
    score_strategy: str | None = None,
) -> str:
    strategy = score_strategy or (objective_kwargs or {}).get("score_strategy") or DEFAULT_SCORE_STRATEGY
    if strategy not in {LEGACY_SCORE_STRATEGY, STABLE_SCORE_STRATEGY}:
        raise ValueError(
            f"Unsupported score strategy '{strategy}'. "
            f"Use '{LEGACY_SCORE_STRATEGY}' or '{STABLE_SCORE_STRATEGY}'."
        )
    return strategy


def _normalize_weight_keys(raw: dict[str, Any]) -> dict[str, Any]:
    normalized = {}
    for key, value in raw.items():
        normalized_key = STABLE_WEIGHT_ALIASES.get(key, key)
        normalized[normalized_key] = value
    return normalized


def _resolve_stable_weight_inputs(
    objective_kwargs: dict[str, Any] | None = None,
    *,
    score_weights: dict[str, Any] | StableScoreWeights | None = None,
) -> tuple[dict[str, float], dict[str, float]]:
    weight_defaults = asdict(StableScoreWeights())
    merged_inputs = dict(weight_defaults)

    raw_weights = (objective_kwargs or {}).get("weights")
    if raw_weights:
        merged_inputs.update(_normalize_weight_keys(dict(raw_weights)))

    if isinstance(score_weights, StableScoreWeights):
        merged_inputs.update(asdict(score_weights))
    elif score_weights:
        merged_inputs.update(_normalize_weight_keys(dict(score_weights)))

    clean = {}
    for key, default_value in weight_defaults.items():
        value = _safe_float(merged_inputs.get(key), default=default_value)
        if value < 0:
            raise ValueError(f"Weight '{key}' must be non-negative.")
        clean[key] = value

    total = sum(clean.values())
    if total <= 0:
        raise ValueError("At least one score weight must be greater than zero.")
    normalized = {key: float(value / total) for key, value in clean.items()}
    return clean, normalized


def resolve_legacy_objective_config(
    objective_kwargs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = deepcopy(DEFAULT_LEGACY_OBJECTIVE_CONFIG)
    if objective_kwargs:
        filtered = {
            key: value
            for key, value in objective_kwargs.items()
            if key
            not in {
                "score_strategy",
                "weights",
                "normalization_strategy",
                "normalization",
                "woe_shrinkage_strength",
            }
        }
        _deep_update(config, filtered)
    config["score_strategy"] = LEGACY_SCORE_STRATEGY
    config["objective_direction"] = "maximize"
    return config


def resolve_stable_objective_config(
    objective_kwargs: dict[str, Any] | None = None,
    *,
    score_weights: dict[str, Any] | StableScoreWeights | None = None,
    normalization_strategy: str | None = None,
    woe_shrinkage_strength: float | None = None,
) -> dict[str, Any]:
    config = asdict(StableObjectiveConfig())

    if objective_kwargs:
        filtered = {
            key: value
            for key, value in objective_kwargs.items()
            if key not in {"score_strategy", "weights"}
        }
        _deep_update(config, filtered)

    raw_weight_inputs, normalized_weights = _resolve_stable_weight_inputs(
        objective_kwargs,
        score_weights=score_weights,
    )

    if normalization_strategy is not None:
        config["normalization_strategy"] = normalization_strategy
    if woe_shrinkage_strength is not None:
        config["woe_shrinkage_strength"] = _safe_float(woe_shrinkage_strength, default=25.0)

    config["score_strategy"] = STABLE_SCORE_STRATEGY
    config["objective_direction"] = "minimize"
    config["woe_shrinkage_strength"] = max(
        _safe_float(config.get("woe_shrinkage_strength"), default=25.0),
        0.0,
    )
    config["weights_input"] = raw_weight_inputs
    config["weights"] = normalized_weights
    return config


def resolve_objective_config(
    objective_kwargs: dict[str, Any] | None = None,
    *,
    score_strategy: str | None = None,
    score_weights: dict[str, Any] | StableScoreWeights | None = None,
    normalization_strategy: str | None = None,
    woe_shrinkage_strength: float | None = None,
) -> dict[str, Any]:
    strategy = resolve_score_strategy(objective_kwargs, score_strategy=score_strategy)
    if strategy == LEGACY_SCORE_STRATEGY:
        return resolve_legacy_objective_config(objective_kwargs)

    return resolve_stable_objective_config(
        objective_kwargs,
        score_weights=score_weights,
        normalization_strategy=normalization_strategy,
        woe_shrinkage_strength=woe_shrinkage_strength,
    )


def resolve_objective_direction(
    objective_kwargs: dict[str, Any] | None = None,
    *,
    score_strategy: str | None = None,
) -> str:
    config = resolve_objective_config(objective_kwargs, score_strategy=score_strategy)
    return str(config.get("objective_direction", "maximize"))


def _require_single_variable(bin_summary: pd.DataFrame) -> str:
    if bin_summary is None or bin_summary.empty:
        raise RuntimeError("Binner ainda nao foi treinado.")
    return str(bin_summary["variable"].iloc[0])


def _resolve_bin_summary_frame(binner) -> pd.DataFrame:
    bin_summary = getattr(binner, "bin_summary", None)
    if bin_summary is None:
        bin_summary = getattr(binner, "bin_summary_", None)
    if bin_summary is None:
        raise AttributeError("The provided binner does not expose `bin_summary` or `bin_summary_`.")
    return bin_summary


def _resolve_count_series(binner) -> pd.Series:
    bin_summary = _resolve_bin_summary_frame(binner)
    for column in ("count", "Count"):
        if column in bin_summary.columns:
            return pd.to_numeric(bin_summary[column], errors="coerce").fillna(0.0)
    raise KeyError("The provided binner does not expose a recognized count column.")


def _build_legacy_objective_components(
    binner,
    X: pd.DataFrame,
    y: pd.Series,
    *,
    time_col: str | None = None,
    objective_kwargs: dict[str, Any] | None = None,
) -> dict[str, float]:
    config = resolve_legacy_objective_config(objective_kwargs)
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

    variable = _require_single_variable(_resolve_bin_summary_frame(binner))
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


def _resolve_single_variable_diagnostics(
    binner,
    X: pd.DataFrame,
    y: pd.Series,
    *,
    time_col: str | None,
    objective_kwargs: dict[str, Any] | None = None,
) -> tuple[pd.DataFrame | None, dict[str, float]]:
    components = {
        "iv": _safe_float(getattr(binner, "iv_", 0.0)),
        "ks": 0.0,
        "temporal_score": 0.0,
        "coverage_ratio_mean": 1.0,
        "coverage_ratio_min": 1.0,
        "n_bins_effective": 0.0,
        "rare_bin_count": 0.0,
    }
    if not time_col or time_col not in X.columns:
        return None, components

    config = resolve_stable_objective_config(objective_kwargs)
    diagnostics_cfg = config["diagnostics"]
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
            "coverage_ratio_mean",
            "coverage_ratio_min",
            "n_bins_effective",
            "rare_bin_count",
        ):
            components[column] = _safe_float(row.get(column, components[column]))

    pivot = (
        diagnostics.pivot_table(index="bin_code", columns=time_col, values="event_rate")
        .sort_index(axis=1)
        .sort_index()
    )
    components["ks"] = _safe_float(ks_over_time(pivot))
    return diagnostics, components


def _entropy_penalty_from_counts(counts: pd.Series) -> float:
    values = counts.astype(float)
    values = values[values > 0]
    if values.empty or len(values) <= 1:
        return 1.0
    probs = values / values.sum()
    entropy = float(-(probs * np.log(np.clip(probs, EPSILON, None))).sum())
    entropy_max = np.log(len(probs))
    if entropy_max <= 0:
        return 1.0
    entropy_norm = entropy / entropy_max
    return float(np.clip(1.0 - entropy_norm, 0.0, 1.0))


def _prepare_stable_frames(
    diagnostics: pd.DataFrame,
    *,
    time_col: str,
    woe_shrinkage_strength: float,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    df = diagnostics.copy().sort_values(["bin_order", time_col]).reset_index(drop=True)
    df["bin_code"] = df["bin_code"].astype(float)

    period_totals = (
        df.groupby(time_col)[["event_count", "non_event_count", "total_count"]]
        .sum()
        .rename(
            columns={
                "event_count": "period_event_count",
                "non_event_count": "period_non_event_count",
                "total_count": "period_total_count",
            }
        )
        .reset_index()
    )
    df = df.merge(period_totals, on=time_col, how="left")

    global_bin_totals = (
        df.groupby("bin_code")[["event_count", "non_event_count", "total_count"]]
        .sum()
        .rename(
            columns={
                "event_count": "global_event_count",
                "non_event_count": "global_non_event_count",
                "total_count": "global_total_count",
            }
        )
    )

    global_event_total = max(_safe_float(global_bin_totals["global_event_count"].sum()), 1.0)
    global_non_event_total = max(_safe_float(global_bin_totals["global_non_event_count"].sum()), 1.0)
    global_bin_totals["global_woe"] = np.log(
        _clip_ratio(global_bin_totals["global_event_count"].to_numpy() / global_event_total)
        / _clip_ratio(global_bin_totals["global_non_event_count"].to_numpy() / global_non_event_total)
    )

    df = df.merge(global_bin_totals[["global_woe", "global_total_count"]], on="bin_code", how="left")

    if woe_shrinkage_strength <= 0:
        reliability = np.where(df["coverage_flag"], 1.0, 0.0)
    else:
        reliability = np.where(
            df["coverage_flag"],
            df["total_count"] / (df["total_count"] + woe_shrinkage_strength),
            0.0,
        )
    raw_woe = df["woe"].astype(float).to_numpy()
    anchor = df["global_woe"].astype(float).to_numpy()
    df["woe_shrunk"] = np.where(
        df["coverage_flag"],
        reliability * np.where(np.isfinite(raw_woe), raw_woe, anchor) + (1.0 - reliability) * anchor,
        np.nan,
    )

    total_volume = max(_safe_float(global_bin_totals["global_total_count"].sum()), 1.0)
    bin_weights = (
        global_bin_totals["global_total_count"] / total_volume
    ) * (1.0 + np.abs(global_bin_totals["global_woe"]))
    if _safe_float(bin_weights.sum()) <= 0:
        bin_weights = pd.Series(1.0, index=global_bin_totals.index)
    bin_weights = (bin_weights / bin_weights.sum()).rename("bin_weight")

    return df, global_bin_totals, bin_weights


def _compute_temporal_variance(df: pd.DataFrame, bin_weights: pd.Series) -> float:
    variances = []
    weights = []
    for bin_code, grp in df.groupby("bin_code", sort=True):
        mask = grp["coverage_flag"] & grp["woe_shrunk"].notna()
        values = grp.loc[mask, "woe_shrunk"].to_numpy(dtype=float)
        support = grp.loc[mask, "total_count"].to_numpy(dtype=float)
        variances.append(_weighted_variance(values, support))
        weights.append(_safe_float(bin_weights.get(bin_code), default=0.0))
    return _weighted_mean(np.asarray(variances, dtype=float), np.asarray(weights, dtype=float))


def _compute_window_drift(
    df: pd.DataFrame,
    *,
    time_col: str,
    bin_weights: pd.Series,
) -> float:
    pivot = (
        df.pivot_table(index="bin_code", columns=time_col, values="woe_shrunk")
        .sort_index(axis=1)
        .sort_index()
    )
    if pivot.shape[1] < 2:
        return 0.0

    drifts = []
    for left, right in zip(pivot.columns[:-1], pivot.columns[1:], strict=False):
        left_values = pivot[left]
        right_values = pivot[right]
        mask = left_values.notna() & right_values.notna()
        if not mask.any():
            continue
        diffs = np.abs(left_values.loc[mask].to_numpy(dtype=float) - right_values.loc[mask].to_numpy(dtype=float))
        weights = np.asarray(
            [bin_weights.get(bin_code, 0.0) for bin_code in left_values.loc[mask].index],
            dtype=float,
        )
        drifts.append(_weighted_mean(diffs, weights))
    if not drifts:
        return 0.0
    return float(np.mean(drifts))


def _compute_rank_inversion_penalty(
    df: pd.DataFrame,
    *,
    time_col: str,
    global_bin_totals: pd.DataFrame,
    bin_weights: pd.Series,
) -> float:
    ordered_periods = sorted(df[time_col].dropna().unique().tolist())
    if len(ordered_periods) < 2:
        return 0.0

    def _build_pair_signs(score_map: dict[float, float]) -> list[tuple[float, float, float, float]]:
        pairs = []
        bin_codes = sorted(score_map)
        for left_idx, left_code in enumerate(bin_codes):
            for right_code in bin_codes[left_idx + 1 :]:
                reference_sign = float(np.sign(score_map[left_code] - score_map[right_code]))
                if reference_sign == 0:
                    continue
                pair_weight = 0.5 * (
                    _safe_float(bin_weights.get(left_code), default=0.0)
                    + _safe_float(bin_weights.get(right_code), default=0.0)
                )
                pairs.append((left_code, right_code, reference_sign, pair_weight))
        return pairs

    def _period_score_map(period_df: pd.DataFrame) -> dict[float, float]:
        covered = period_df.loc[period_df["coverage_flag"] & period_df["woe_shrunk"].notna()]
        return covered.set_index("bin_code")["woe_shrunk"].to_dict()

    def _pair_penalty(
        reference_pairs: list[tuple[float, float, float, float]],
        current_map: dict[float, float],
    ) -> float:
        inverted = 0.0
        total = 0.0
        for left_code, right_code, reference_sign, pair_weight in reference_pairs:
            if left_code not in current_map or right_code not in current_map:
                continue
            current_sign = float(np.sign(current_map[left_code] - current_map[right_code]))
            if current_sign == 0:
                continue
            total += pair_weight
            if current_sign != reference_sign:
                inverted += pair_weight
        return inverted / total if total > 0 else 0.0

    by_period = {
        period: grp.copy()
        for period, grp in df.groupby(time_col, sort=True)
    }
    first_period = ordered_periods[0]
    reference_map = _period_score_map(by_period[first_period])
    reference_pairs = _build_pair_signs(reference_map)
    if not reference_pairs:
        global_pairs = _build_pair_signs(global_bin_totals["global_woe"].sort_index().to_dict())
        reference_pairs = global_pairs

    reference_penalties = []
    reference_weights = []
    for period in ordered_periods[1:]:
        current_map = _period_score_map(by_period[period])
        penalty = _pair_penalty(reference_pairs, current_map)
        reference_penalties.append(penalty)
        reference_weights.append(_safe_float(by_period[period]["period_total_count"].iloc[0], default=1.0))

    adjacent_penalties = []
    adjacent_weights = []
    for left_period, right_period in zip(ordered_periods[:-1], ordered_periods[1:], strict=False):
        left_map = _period_score_map(by_period[left_period])
        right_map = _period_score_map(by_period[right_period])
        adjacent_pairs = _build_pair_signs(left_map)
        if not adjacent_pairs:
            continue
        adjacent_penalties.append(_pair_penalty(adjacent_pairs, right_map))
        adjacent_weights.append(_safe_float(by_period[right_period]["period_total_count"].iloc[0], default=1.0))

    reference_score = _weighted_mean(
        np.asarray(reference_penalties, dtype=float),
        np.asarray(reference_weights, dtype=float),
    )
    adjacent_score = _weighted_mean(
        np.asarray(adjacent_penalties, dtype=float),
        np.asarray(adjacent_weights, dtype=float),
    )
    return float(0.5 * reference_score + 0.5 * adjacent_score)


def _compute_separation_metrics(df: pd.DataFrame, *, time_col: str) -> tuple[float, float]:
    event_prop = np.where(
        df["coverage_flag"],
        df["event_count"] / np.clip(df["period_event_count"], 1, None),
        0.0,
    )
    non_event_prop = np.where(
        df["coverage_flag"],
        df["non_event_count"] / np.clip(df["period_non_event_count"], 1, None),
        0.0,
    )
    df_iv = df.copy()
    df_iv["iv_contribution_shrunk"] = np.where(
        df["coverage_flag"],
        (event_prop - non_event_prop) * np.nan_to_num(df["woe_shrunk"], nan=0.0),
        0.0,
    )
    period_iv = df_iv.groupby(time_col)["iv_contribution_shrunk"].sum()
    if period_iv.empty:
        return 0.0, 0.0
    period_weights = (
        df_iv.groupby(time_col)["period_total_count"].first().reindex(period_iv.index).to_numpy(dtype=float)
    )
    values = period_iv.to_numpy(dtype=float)
    return _weighted_mean(values, period_weights), np.sqrt(_weighted_variance(values, period_weights))


def _compute_entropy_penalty(diagnostics: pd.DataFrame) -> float:
    counts = diagnostics.groupby("bin_code")["total_count"].sum()
    return _entropy_penalty_from_counts(counts)


def _compute_psi_metrics(df: pd.DataFrame, *, time_col: str) -> tuple[float, float, float]:
    share_pivot = (
        df.pivot_table(index="bin_code", columns=time_col, values="bin_share", fill_value=0.0)
        .sort_index(axis=1)
        .sort_index()
    )
    if share_pivot.shape[1] < 2:
        return 0.0, 0.0, 0.0

    adjacent = []
    for left, right in zip(share_pivot.columns[:-1], share_pivot.columns[1:], strict=False):
        adjacent.append(_psi_from_arrays(share_pivot[left].values, share_pivot[right].values))

    reference = _psi_from_arrays(share_pivot.iloc[:, 0].values, share_pivot.iloc[:, -1].values)
    adjacent_mean = float(np.mean(adjacent)) if adjacent else 0.0
    combined = 0.5 * adjacent_mean + 0.5 * reference
    return float(combined), adjacent_mean, float(reference)


def _build_stable_objective_components(
    binner,
    X: pd.DataFrame,
    y: pd.Series,
    *,
    time_col: str | None = None,
    objective_kwargs: dict[str, Any] | None = None,
) -> dict[str, float]:
    config = resolve_stable_objective_config(objective_kwargs)
    diagnostics, summary_components = _resolve_single_variable_diagnostics(
        binner,
        X,
        y,
        time_col=time_col,
        objective_kwargs=config,
    )
    components = {
        **summary_components,
        "temporal_variance": 0.0,
        "window_drift": 0.0,
        "rank_inversion": 0.0,
        "separation": _safe_float(summary_components.get("iv"), default=0.0),
        "entropy": _entropy_penalty_from_counts(_resolve_count_series(binner)),
        "psi": 0.0,
        "period_iv_std": 0.0,
        "psi_adjacent_mean": 0.0,
        "psi_reference": 0.0,
        "n_periods": 0.0,
    }

    if diagnostics is None or not time_col or time_col not in X.columns:
        return components

    df, global_bin_totals, bin_weights = _prepare_stable_frames(
        diagnostics,
        time_col=time_col,
        woe_shrinkage_strength=config["woe_shrinkage_strength"],
    )
    separation_mean, separation_std = _compute_separation_metrics(df, time_col=time_col)
    psi_value, psi_adjacent_mean, psi_reference = _compute_psi_metrics(df, time_col=time_col)

    components.update(
        {
            "temporal_variance": _compute_temporal_variance(df, bin_weights),
            "window_drift": _compute_window_drift(df, time_col=time_col, bin_weights=bin_weights),
            "rank_inversion": _compute_rank_inversion_penalty(
                df,
                time_col=time_col,
                global_bin_totals=global_bin_totals,
                bin_weights=bin_weights,
            ),
            "separation": separation_mean,
            "entropy": _compute_entropy_penalty(df),
            "psi": psi_value,
            "period_iv_std": separation_std,
            "psi_adjacent_mean": psi_adjacent_mean,
            "psi_reference": psi_reference,
            "n_periods": float(df[time_col].nunique()),
        }
    )
    return components


def build_objective_components(
    binner,
    X: pd.DataFrame,
    y: pd.Series,
    *,
    time_col: str | None = None,
    objective_kwargs: dict[str, Any] | None = None,
    score_strategy: str | None = None,
    score_weights: dict[str, Any] | StableScoreWeights | None = None,
    normalization_strategy: str | None = None,
    woe_shrinkage_strength: float | None = None,
) -> dict[str, float]:
    config = resolve_objective_config(
        objective_kwargs,
        score_strategy=score_strategy,
        score_weights=score_weights,
        normalization_strategy=normalization_strategy,
        woe_shrinkage_strength=woe_shrinkage_strength,
    )
    if config["score_strategy"] == LEGACY_SCORE_STRATEGY:
        return _build_legacy_objective_components(
            binner,
            X,
            y,
            time_col=time_col,
            objective_kwargs=config,
        )
    return _build_stable_objective_components(
        binner,
        X,
        y,
        time_col=time_col,
        objective_kwargs=config,
    )


def _curve_separation_from_pivot(pivot: pd.DataFrame) -> float:
    if pivot.shape[0] < 2:
        return 0.0
    curves = pivot.to_numpy(dtype=float)
    distances = []
    for left_idx in range(pivot.shape[0]):
        for right_idx in range(left_idx + 1, pivot.shape[0]):
            diffs = curves[left_idx] - curves[right_idx]
            mask = np.isfinite(diffs)
            if mask.sum() == 0:
                continue
            distances.append(float(np.abs(diffs[mask]).mean()))
    return float(np.mean(distances)) if distances else 0.0


def build_objective_components_from_diagnostics(
    diagnostics: pd.DataFrame,
    *,
    iv_value: float = 0.0,
    summary_row: dict[str, Any] | None = None,
    time_col: str | None = None,
    objective_kwargs: dict[str, Any] | None = None,
    score_strategy: str | None = None,
    score_weights: dict[str, Any] | StableScoreWeights | None = None,
    normalization_strategy: str | None = None,
    woe_shrinkage_strength: float | None = None,
) -> dict[str, float]:
    config = resolve_objective_config(
        objective_kwargs,
        score_strategy=score_strategy,
        score_weights=score_weights,
        normalization_strategy=normalization_strategy,
        woe_shrinkage_strength=woe_shrinkage_strength,
    )
    summary_row = summary_row or {}
    time_col = time_col or diagnostics.attrs.get("time_col")
    if not time_col or time_col not in diagnostics.columns:
        raise ValueError("time_col must be provided or present in diagnostics attrs.")

    if config["score_strategy"] == LEGACY_SCORE_STRATEGY:
        pivot = (
            diagnostics.pivot_table(index="bin_code", columns=time_col, values="event_rate")
            .sort_index(axis=1)
            .sort_index()
        )
        components = {
            "iv": _safe_float(iv_value),
            "separability": _curve_separation_from_pivot(pivot),
            "ks": _safe_float(ks_over_time(pivot)),
            "temporal_score": _safe_float(summary_row.get("temporal_score")),
            "n_bins_effective": _safe_float(summary_row.get("n_bins_effective")),
            "coverage_ratio_min": _safe_float(summary_row.get("coverage_ratio_min"), default=1.0),
            "coverage_ratio_mean": _safe_float(summary_row.get("coverage_ratio_mean"), default=1.0),
            "rare_bin_count": _safe_float(summary_row.get("rare_bin_count")),
            "event_rate_std_mean": _safe_float(summary_row.get("event_rate_std_mean")),
            "event_rate_std_max": _safe_float(summary_row.get("event_rate_std_max")),
            "woe_std_mean": _safe_float(summary_row.get("woe_std_mean")),
            "woe_std_max": _safe_float(summary_row.get("woe_std_max")),
            "bin_share_std_mean": _safe_float(summary_row.get("bin_share_std_mean")),
            "bin_share_std_max": _safe_float(summary_row.get("bin_share_std_max")),
            "monotonic_break_period_count": _safe_float(summary_row.get("monotonic_break_period_count")),
            "ranking_reversal_period_count": _safe_float(summary_row.get("ranking_reversal_period_count")),
            "bins_missing_any_period_count": _safe_float(summary_row.get("bins_missing_any_period_count")),
            "missing_period_count": _safe_float(summary_row.get("missing_period_count")),
            "low_coverage_bin_count": _safe_float(summary_row.get("low_coverage_bin_count")),
        }
        return components

    components = {
        "iv": _safe_float(iv_value),
        "ks": 0.0,
        "temporal_score": _safe_float(summary_row.get("temporal_score")),
        "coverage_ratio_mean": _safe_float(summary_row.get("coverage_ratio_mean"), default=1.0),
        "coverage_ratio_min": _safe_float(summary_row.get("coverage_ratio_min"), default=1.0),
        "n_bins_effective": _safe_float(summary_row.get("n_bins_effective")),
        "rare_bin_count": _safe_float(summary_row.get("rare_bin_count")),
        "temporal_variance": 0.0,
        "window_drift": 0.0,
        "rank_inversion": 0.0,
        "separation": _safe_float(iv_value),
        "entropy": _compute_entropy_penalty(diagnostics),
        "psi": 0.0,
        "period_iv_std": 0.0,
        "psi_adjacent_mean": 0.0,
        "psi_reference": 0.0,
        "n_periods": float(diagnostics[time_col].nunique()),
    }
    pivot = (
        diagnostics.pivot_table(index="bin_code", columns=time_col, values="event_rate")
        .sort_index(axis=1)
        .sort_index()
    )
    components["ks"] = _safe_float(ks_over_time(pivot))

    df, global_bin_totals, bin_weights = _prepare_stable_frames(
        diagnostics,
        time_col=time_col,
        woe_shrinkage_strength=config["woe_shrinkage_strength"],
    )
    separation_mean, separation_std = _compute_separation_metrics(df, time_col=time_col)
    psi_value, psi_adjacent_mean, psi_reference = _compute_psi_metrics(df, time_col=time_col)
    components.update(
        {
            "temporal_variance": _compute_temporal_variance(df, bin_weights),
            "window_drift": _compute_window_drift(df, time_col=time_col, bin_weights=bin_weights),
            "rank_inversion": _compute_rank_inversion_penalty(
                df,
                time_col=time_col,
                global_bin_totals=global_bin_totals,
                bin_weights=bin_weights,
            ),
            "separation": separation_mean,
            "psi": psi_value,
            "period_iv_std": separation_std,
            "psi_adjacent_mean": psi_adjacent_mean,
            "psi_reference": psi_reference,
        }
    )
    return components


def _score_legacy_objective_components(
    components: dict[str, Any],
    *,
    objective_kwargs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = resolve_legacy_objective_config(objective_kwargs)
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
        "comparison_score": float(score),
        "objective_direction": "maximize",
        "score_strategy": LEGACY_SCORE_STRATEGY,
        "components": comps,
        "normalized_components": {},
        "weights": {},
        "base_components": base_components,
        "penalties": penalties,
        "minimum_checks": minimum_checks,
        "objective_config": config,
    }


def _score_stable_objective_components(
    components: dict[str, Any],
    *,
    objective_kwargs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = resolve_stable_objective_config(objective_kwargs)
    if config["normalization_strategy"] != "absolute":
        raise ValueError(
            f"Unsupported normalization strategy '{config['normalization_strategy']}'. "
            "Only 'absolute' is currently implemented."
        )

    comps = {key: _safe_float(value) for key, value in components.items()}
    normalization = config["normalization"]

    separation_reward_norm = _saturating_normalize(
        comps.get("separation", 0.0),
        scale=normalization["separation_scale"],
    )
    normalized_components = {
        "temporal_variance": _saturating_normalize(
            comps.get("temporal_variance", 0.0),
            scale=normalization["temporal_variance_scale"],
        ),
        "window_drift": _saturating_normalize(
            comps.get("window_drift", 0.0),
            scale=normalization["window_drift_scale"],
        ),
        "rank_inversion": _bounded_normalize(comps.get("rank_inversion", 0.0)),
        "separation_reward": separation_reward_norm,
        "separation_penalty": float(1.0 - separation_reward_norm),
        "entropy": _bounded_normalize(comps.get("entropy", 0.0)),
        "psi": _saturating_normalize(
            comps.get("psi", 0.0),
            scale=normalization["psi_scale"],
        ),
    }

    weights = config["weights"]
    base_components = {
        "separation_reward_component": weights["separation_weight"]
        * normalized_components["separation_reward"],
    }
    penalties = {
        "temporal_variance_penalty": weights["temporal_variance_weight"]
        * normalized_components["temporal_variance"],
        "window_drift_penalty": weights["window_drift_weight"]
        * normalized_components["window_drift"],
        "rank_inversion_penalty": weights["rank_inversion_weight"]
        * normalized_components["rank_inversion"],
        "separation_penalty": weights["separation_weight"]
        * normalized_components["separation_penalty"],
        "entropy_penalty": weights["entropy_weight"]
        * normalized_components["entropy"],
        "psi_penalty": weights["psi_weight"] * normalized_components["psi"],
    }

    base_score = float(sum(base_components.values()))
    score = float(sum(penalties.values()))
    if not np.isfinite(score):
        score = 1e6

    minimum_checks = {
        "has_temporal_information": comps.get("n_periods", 0.0) >= 2,
        "has_minimum_coverage": comps.get("coverage_ratio_min", 1.0)
        >= config["diagnostics"]["min_time_coverage"],
    }

    return {
        "score": score,
        "base_score": base_score,
        "total_penalty": score,
        "comparison_score": float(-score),
        "objective_direction": "minimize",
        "score_strategy": STABLE_SCORE_STRATEGY,
        "components": comps,
        "normalized_components": normalized_components,
        "weights": weights,
        "base_components": base_components,
        "penalties": penalties,
        "minimum_checks": minimum_checks,
        "woe_shrinkage": {
            "strength": config["woe_shrinkage_strength"],
            "anchor": "global_bin_woe",
        },
        "objective_config": config,
    }


def score_objective_components(
    components: dict[str, Any],
    *,
    objective_kwargs: dict[str, Any] | None = None,
    score_strategy: str | None = None,
    score_weights: dict[str, Any] | StableScoreWeights | None = None,
    normalization_strategy: str | None = None,
    woe_shrinkage_strength: float | None = None,
) -> dict[str, Any]:
    config = resolve_objective_config(
        objective_kwargs,
        score_strategy=score_strategy,
        score_weights=score_weights,
        normalization_strategy=normalization_strategy,
        woe_shrinkage_strength=woe_shrinkage_strength,
    )
    if config["score_strategy"] == LEGACY_SCORE_STRATEGY:
        return _score_legacy_objective_components(components, objective_kwargs=config)
    return _score_stable_objective_components(components, objective_kwargs=config)
