"""Auditable report generation for RiskBands objects."""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timezone
from importlib.util import find_spec
from pathlib import Path
from typing import Any, Union

import numpy as np
import pandas as pd

from ._version import resolve_version
from .binning_engine import Binner
from .objectives import (
    build_objective_components,
    build_objective_components_from_diagnostics,
    resolve_objective_config,
    resolve_score_strategy,
    score_objective_components,
)
from .temporal_stability import event_rate_by_time, ks_over_time, temporal_separability_score

PathLike = Union[str, Path]

BASE_COMPONENT_COLUMNS = [
    "separability_component",
    "iv_component",
    "ks_component",
    "temporal_score_component",
]

GENERALIZATION_BASE_COMPONENT_COLUMNS = [
    "separation_reward_component",
]

PENALTY_COLUMNS = [
    "rare_bin_penalty",
    "coverage_gap_penalty",
    "event_rate_volatility_penalty",
    "woe_volatility_penalty",
    "share_volatility_penalty",
    "monotonic_break_penalty",
    "ranking_reversal_penalty",
    "iv_shortfall_penalty",
    "temporal_shortfall_penalty",
]

GENERALIZATION_PENALTY_COLUMNS = [
    "temporal_variance_penalty",
    "window_drift_penalty",
    "rank_inversion_penalty",
    "separation_penalty",
    "entropy_penalty",
    "psi_penalty",
]

TEMPORAL_PROFILE_PENALTIES = [
    "rare_bin_penalty",
    "coverage_gap_penalty",
    "event_rate_volatility_penalty",
    "woe_volatility_penalty",
    "share_volatility_penalty",
    "monotonic_break_penalty",
    "ranking_reversal_penalty",
    "temporal_shortfall_penalty",
    "temporal_variance_penalty",
    "window_drift_penalty",
    "rank_inversion_penalty",
    "psi_penalty",
]

_SAFE_ARTIFACT_RE = re.compile(r"[^A-Za-z0-9._-]+")
_SAFE_ARTIFACT_MAX_LENGTH = 100
_WINDOWS_RESERVED_FILENAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}

BUNDLE_SCHEMA_VERSION = "2.1"
LEGACY_BUNDLE_SCHEMA_VERSION = "1.0"
OPTIONAL_BUNDLE_PROFILE_FIELDS = (
    "fit_profile",
    "source_profile",
    "reference_profile",
    "reference_profile_source",
    "application_profile",
    "fit_validation_report",
    "transform_validation_report",
    "validation_report",
    "sampling_metadata",
    "backend_metadata",
    "min_n_bins_metadata",
    "validation_settings",
    "data_schema",
    "missing_policy",
    "effective_missing_policy",
    "missing_merge_criterion",
    "missing_merge_fallback",
    "missing_profile",
    "missing_decision_log",
    "missing_merge_candidates",
    "missing_merge_map",
    "missing_transform_fallback_log",
)


def _require_bin_summary(binner: Binner) -> pd.DataFrame:
    bin_summary = getattr(binner, "bin_summary", None)
    if bin_summary is None:
        raise RuntimeError("Binner ainda nao foi treinado.")
    return bin_summary


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


def _coalesce_text(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text and text.lower() != "nan":
            return text
    return ""


def _candidate_name(candidate_name: str | None) -> str:
    return candidate_name or "selected_candidate"


def _safe_artifact_name(name: object, *, fallback: str = "feature") -> str:
    text = unicodedata.normalize("NFKD", str(name))
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.replace("/", "_").replace("\\", "_")
    while ".." in text:
        text = text.replace("..", "_")
    text = _SAFE_ARTIFACT_RE.sub("_", text)
    text = re.sub(r"_+", "_", text).strip("._- ")

    if not text:
        text = _SAFE_ARTIFACT_RE.sub("_", str(fallback)).strip("._- ") or "feature"

    text = text[:_SAFE_ARTIFACT_MAX_LENGTH].rstrip("._- ")
    if not text:
        text = "feature"
    if text.upper().split(".", 1)[0] in _WINDOWS_RESERVED_FILENAMES:
        text = f"{text}_"
    return text


def _unique_artifact_name(stem: str, used_names: set[str]) -> str:
    candidate = stem
    counter = 2
    while candidate in used_names:
        suffix = f"_{counter}"
        prefix = stem[: _SAFE_ARTIFACT_MAX_LENGTH - len(suffix)].rstrip("._- ")
        candidate = f"{prefix or 'feature'}{suffix}"
        counter += 1
    used_names.add(candidate)
    return candidate


def _ensure_path_inside(base: Path, candidate: Path) -> Path:
    base_resolved = base.resolve()
    candidate_resolved = candidate.resolve()
    if candidate_resolved != base_resolved and base_resolved not in candidate_resolved.parents:
        raise ValueError(f"Refusing to write outside target directory: {candidate}")
    return candidate


def _resolve_child_binner(
    binner: Binner, variable: str
) -> Binner:
    if hasattr(binner, "_per_feature_binners") and variable in getattr(binner, "_per_feature_binners", {}):
        return binner._per_feature_binners[variable]
    return binner


def _bin_rows_for_variable(bin_summary: pd.DataFrame, variable: str) -> pd.DataFrame:
    rows = bin_summary.loc[bin_summary["variable"] == variable].copy()
    if rows.empty:
        raise KeyError(f"Variable '{variable}' not found in bin_summary.")

    for candidate in ("bin_order", "bin_code", "bin_code_float", "bin_code_int"):
        if candidate in rows.columns:
            return rows.sort_values(candidate).reset_index(drop=True)

    return rows.reset_index(drop=True)


def _cut_summary(bin_rows: pd.DataFrame) -> str:
    labels = [str(value) for value in bin_rows["bin"].tolist()]
    return " | ".join(labels)


def _top_items(mapping: dict[str, Any] | None, *, limit: int = 3) -> str:
    items = []
    for key, value in (mapping or {}).items():
        score = _safe_float(value)
        if score > 0:
            items.append((key, score))

    if not items:
        return "none"

    items.sort(key=lambda item: item[1], reverse=True)
    return "; ".join(f"{name}={value:.3f}" for name, value in items[:limit])


def _selection_basis(base_components: dict[str, Any] | None) -> str:
    base_components = base_components or {}
    if _safe_float(base_components.get("separation_reward_component")) > 0:
        return "balanced"

    static_signal = _safe_float(base_components.get("iv_component")) + _safe_float(
        base_components.get("ks_component")
    )
    temporal_signal = _safe_float(base_components.get("temporal_score_component")) + _safe_float(
        base_components.get("separability_component")
    )

    if static_signal <= 0 and temporal_signal <= 0:
        return "no_objective_signal"
    if temporal_signal > static_signal * 1.2:
        return "stability-led"
    if static_signal > temporal_signal * 1.2:
        return "discrimination-led"
    return "balanced"


def _basis_text(selection_basis: str) -> str:
    mapping = {
        "balanced": "Venceu por equilibrio entre discriminacao e estabilidade temporal.",
        "stability-led": "Venceu mais pela estabilidade temporal do que pelo ganho estatico.",
        "discrimination-led": "Venceu mais pela discriminacao estatica do que pela estabilidade temporal.",
        "no_objective_signal": "Resumo baseado nas metricas observadas, sem score de objetivo rastreavel.",
    }
    return mapping.get(selection_basis, mapping["balanced"])


def _build_rationale_summary(row: dict[str, Any]) -> str:
    parts = [_basis_text(str(row.get("selection_basis", "balanced")))]

    key_drivers = _coalesce_text(row.get("key_drivers"))
    if key_drivers and key_drivers != "none":
        parts.append(f"Drivers principais: {key_drivers}.")

    key_penalties = _coalesce_text(row.get("key_penalties"))
    if key_penalties and key_penalties != "none":
        parts.append(f"Penalizacoes relevantes: {key_penalties}.")

    alert_flags = _coalesce_text(row.get("alert_flags"))
    if alert_flags:
        parts.append(f"Alertas remanescentes: {alert_flags}.")

    return " ".join(parts)


def _json_ready_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    clean = df.copy()
    clean = clean.where(pd.notna(clean), None)
    return _json_safe(clean.to_dict(orient="records"))


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, pd.Series):
        return {str(key): _json_safe(item) for key, item in value.to_dict().items()}
    if isinstance(value, pd.DataFrame):
        return _json_ready_records(value)
    if isinstance(value, np.ndarray):
        return [_json_safe(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not np.isfinite(value):
        return None
    try:
        if pd.isna(value):
            return None
    except Exception:
        return value
    return value


def _format_key_value_profile(mapping: dict[str, Any] | None) -> str:
    cleaned = []
    for key, value in (mapping or {}).items():
        score = _safe_float(value, default=np.nan)
        if np.isfinite(score):
            cleaned.append((key, float(score)))
    if not cleaned:
        return ""
    return "; ".join(f"{key}={value:.3f}" for key, value in cleaned)


def _resolve_effective_objective_kwargs(
    binner: Binner,
    objective_kwargs: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if objective_kwargs is not None:
        if hasattr(binner, "_resolved_objective_kwargs"):
            return binner._resolved_objective_kwargs(objective_kwargs)
        return objective_kwargs
    if hasattr(binner, "_resolved_objective_kwargs"):
        return binner._resolved_objective_kwargs()
    return getattr(binner, "objective_kwargs", None)


def _objective_preference_score(row: dict[str, Any] | pd.Series) -> float:
    score = _safe_float(row.get("objective_score"), default=np.nan)
    direction = _coalesce_text(row.get("objective_direction")) or "maximize"
    if not np.isfinite(score):
        return np.nan
    return -score if direction == "minimize" else score


def _resolve_temporal_sources(
    binner: Binner,
    X: pd.DataFrame | None,
    y: pd.Series | None,
    *,
    time_col: str | None,
    dataset_name: str | None,
    diagnostics: pd.DataFrame | None,
    summary: pd.DataFrame | None,
) -> tuple[pd.DataFrame | None, pd.DataFrame | None, str | None]:
    diagnostics = diagnostics if diagnostics is not None else getattr(binner, "_temporal_bin_diagnostics_", None)
    summary = summary if summary is not None else getattr(binner, "_temporal_variable_summary_", None)

    if time_col is None:
        if summary is not None:
            time_col = summary.attrs.get("time_col")
        elif diagnostics is not None:
            time_col = diagnostics.attrs.get("time_col")
        else:
            time_col = getattr(binner, "time_col", None)

    if summary is None and diagnostics is not None and not diagnostics.empty and time_col is not None:
        summary = binner.temporal_variable_summary(diagnostics=diagnostics, time_col=time_col)

    if summary is None and X is not None and y is not None and time_col is not None:
        summary = binner.temporal_variable_summary(
            X,
            y,
            time_col=time_col,
            dataset_name=dataset_name,
        )
        diagnostics = getattr(binner, "_temporal_bin_diagnostics_", diagnostics)

    return diagnostics, summary, time_col


def _objective_summary_for_variable(
    binner: Binner,
    variable: str,
    X: pd.DataFrame | None,
    y: pd.Series | None,
    *,
    diagnostics: pd.DataFrame | None,
    time_col: str | None,
    iv_value: float | None,
    summary_row: dict[str, Any] | None,
    objective_kwargs: dict[str, Any] | None,
) -> tuple[dict[str, Any], str]:
    effective_objective_kwargs = _resolve_effective_objective_kwargs(binner, objective_kwargs)
    score_strategy = resolve_score_strategy(
        score_strategy=_coalesce_text(
            (effective_objective_kwargs or {}).get("score_strategy"),
            getattr(binner, "score_strategy", None),
            "standard",
        )
    )
    summaries = getattr(binner, "objective_summaries_", None)
    if isinstance(summaries, dict) and summaries.get(variable):
        return summaries[variable], "stored_multi_feature"

    summary = getattr(binner, "objective_summary_", None)
    if summary:
        return summary, "stored_single_feature"

    if X is None or y is None:
        return {}, "unavailable"

    child_binner = _resolve_child_binner(binner, variable)
    if score_strategy != "standard" and diagnostics is not None and not diagnostics.empty:
        diagnostics_var = diagnostics.loc[diagnostics["variable"] == variable].copy()
        if not diagnostics_var.empty:
            components = build_objective_components_from_diagnostics(
                diagnostics_var,
                iv_value=_safe_float(iv_value, default=0.0),
                summary_row=summary_row,
                time_col=time_col,
                objective_kwargs=effective_objective_kwargs,
            )
            derived = score_objective_components(components, objective_kwargs=effective_objective_kwargs)
            return derived, "derived_from_diagnostics"

    if score_strategy == "standard":
        transformed = child_binner.transform(X[[variable]])
        bin_values = transformed if isinstance(transformed, pd.Series) else transformed[variable]
        components = {
            "iv": _safe_float(iv_value, default=0.0),
            "separability": 0.0,
            "ks": 0.0,
            "temporal_score": _safe_float((summary_row or {}).get("temporal_score"), default=0.0),
            "n_bins_effective": _safe_float((summary_row or {}).get("n_bins_effective"), default=0.0),
            "coverage_ratio_min": _safe_float((summary_row or {}).get("coverage_ratio_min"), default=1.0),
            "coverage_ratio_mean": _safe_float((summary_row or {}).get("coverage_ratio_mean"), default=1.0),
            "rare_bin_count": _safe_float((summary_row or {}).get("rare_bin_count"), default=0.0),
            "event_rate_std_mean": _safe_float((summary_row or {}).get("event_rate_std_mean"), default=0.0),
            "event_rate_std_max": _safe_float((summary_row or {}).get("event_rate_std_max"), default=0.0),
            "woe_std_mean": _safe_float((summary_row or {}).get("woe_std_mean"), default=0.0),
            "woe_std_max": _safe_float((summary_row or {}).get("woe_std_max"), default=0.0),
            "bin_share_std_mean": _safe_float((summary_row or {}).get("bin_share_std_mean"), default=0.0),
            "bin_share_std_max": _safe_float((summary_row or {}).get("bin_share_std_max"), default=0.0),
            "monotonic_break_period_count": _safe_float(
                (summary_row or {}).get("monotonic_break_period_count"),
                default=0.0,
            ),
            "ranking_reversal_period_count": _safe_float(
                (summary_row or {}).get("ranking_reversal_period_count"),
                default=0.0,
            ),
            "bins_missing_any_period_count": _safe_float(
                (summary_row or {}).get("bins_missing_any_period_count"),
                default=0.0,
            ),
            "missing_period_count": _safe_float((summary_row or {}).get("missing_period_count"), default=0.0),
            "low_coverage_bin_count": _safe_float(
                (summary_row or {}).get("low_coverage_bin_count"),
                default=0.0,
            ),
        }

        if time_col and time_col in X.columns:
            df_tmp = pd.DataFrame({"bin": bin_values, "target": y, "time": X[time_col]})
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

        derived = score_objective_components(components, objective_kwargs=effective_objective_kwargs)
        return derived, "derived_standard_objective"

    cols = [variable]
    if time_col and time_col in X.columns:
        cols.append(time_col)
    X_eval = X[cols].copy()

    components = build_objective_components(
        child_binner,
        X_eval,
        y,
        time_col=time_col if time_col in X_eval.columns else None,
        objective_kwargs=effective_objective_kwargs,
    )
    if iv_value is not None:
        components["iv"] = _safe_float(iv_value, default=0.0)
        if (
            score_strategy != "standard"
            and (
                time_col is None
                or time_col not in X_eval.columns
                or X_eval[time_col].nunique(dropna=True) <= 1
            )
        ):
            components["separation"] = _safe_float(iv_value, default=0.0)

    derived = score_objective_components(components, objective_kwargs=effective_objective_kwargs)
    return derived, "derived_configured_objective"


def build_variable_audit_report(
    binner: Binner,
    X: pd.DataFrame | None = None,
    y: pd.Series | None = None,
    *,
    time_col: str | None = None,
    dataset_name: str | None = None,
    diagnostics: pd.DataFrame | None = None,
    summary: pd.DataFrame | None = None,
    candidate_name: str | None = None,
    objective_kwargs: dict[str, Any] | None = None,
) -> pd.DataFrame:
    """
    Build an auditable, variable-level summary of the selected binning.

    The report consolidates:
    - final cut summary
    - static metrics
    - temporal stability metrics
    - objective components and penalties
    - human-readable rationale of the selection
    """
    bin_summary = _require_bin_summary(binner)
    diagnostics, summary, time_col = _resolve_temporal_sources(
        binner,
        X,
        y,
        time_col=time_col,
        dataset_name=dataset_name,
        diagnostics=diagnostics,
        summary=summary,
    )
    iv_by_variable = getattr(binner, "iv_by_variable_", pd.Series(dtype=float))
    effective_objective_kwargs = _resolve_effective_objective_kwargs(binner, objective_kwargs)
    rows = []
    collected_objective_summaries = {}

    for variable in bin_summary["variable"].drop_duplicates().tolist():
        bin_rows = _bin_rows_for_variable(bin_summary, variable)
        child_binner = _resolve_child_binner(binner, variable)
        summary_row = {}
        if summary is not None and not summary.empty:
            match = summary.loc[summary["variable"] == variable]
            if not match.empty:
                summary_row = match.iloc[0].to_dict()

        objective_summary, objective_source = _objective_summary_for_variable(
            binner,
            variable,
            X,
            y,
            diagnostics=diagnostics,
            time_col=time_col,
            iv_value=_safe_float(iv_by_variable.get(variable), default=0.0),
            summary_row=summary_row,
            objective_kwargs=effective_objective_kwargs,
        )
        components = objective_summary.get("components", {})
        base_components = objective_summary.get("base_components", {})
        penalties = objective_summary.get("penalties", {})
        normalized_components = objective_summary.get("normalized_components", {})
        objective_config = objective_summary.get("objective_config", {})
        collected_objective_summaries[variable] = objective_summary

        dataset_value = _coalesce_text(
            summary_row.get("dataset"),
            dataset_name,
            diagnostics.attrs.get("dataset") if diagnostics is not None else None,
        )
        missing_decision_row = {}
        missing_decision_log = getattr(binner, "missing_decision_log_", None)
        if missing_decision_log is not None and not missing_decision_log.empty:
            missing_match = missing_decision_log.loc[missing_decision_log["variable"] == variable]
            if not missing_match.empty:
                missing_decision_row = missing_match.iloc[0].to_dict()

        row = {
            "dataset": dataset_value,
            "variable": variable,
            "candidate_name": _candidate_name(candidate_name),
            "selected_candidate": _candidate_name(candidate_name),
            "selected_strategy": getattr(child_binner, "strategy", getattr(binner, "strategy", "")),
            "cut_summary": _cut_summary(bin_rows),
            "n_bins": int(len(bin_rows)),
            "n_bins_effective": int(_safe_float(summary_row.get("n_bins_effective"), default=len(bin_rows))),
            "iv": _safe_float(iv_by_variable.get(variable, components.get("iv")), default=np.nan),
            "ks": _safe_float(components.get("ks"), default=np.nan),
            "separability": _safe_float(
                components.get("separability", components.get("separation")),
                default=np.nan,
            ),
            "temporal_score": _safe_float(
                summary_row.get("temporal_score", components.get("temporal_score")),
                default=np.nan,
            ),
            "coverage_ratio_mean": _safe_float(summary_row.get("coverage_ratio_mean"), default=np.nan),
            "coverage_ratio_min": _safe_float(summary_row.get("coverage_ratio_min"), default=np.nan),
            "rare_bin_count": int(_safe_float(summary_row.get("rare_bin_count"), default=0.0)),
            "event_rate_std_mean": _safe_float(summary_row.get("event_rate_std_mean"), default=np.nan),
            "event_rate_std_max": _safe_float(summary_row.get("event_rate_std_max"), default=np.nan),
            "woe_std_mean": _safe_float(summary_row.get("woe_std_mean"), default=np.nan),
            "woe_std_max": _safe_float(summary_row.get("woe_std_max"), default=np.nan),
            "bin_share_std_mean": _safe_float(summary_row.get("bin_share_std_mean"), default=np.nan),
            "bin_share_std_max": _safe_float(summary_row.get("bin_share_std_max"), default=np.nan),
            "monotonic_break_period_count": int(
                _safe_float(summary_row.get("monotonic_break_period_count"), default=0.0)
            ),
            "ranking_reversal_period_count": int(
                _safe_float(summary_row.get("ranking_reversal_period_count"), default=0.0)
            ),
            "bins_missing_any_period_count": int(
                _safe_float(summary_row.get("bins_missing_any_period_count"), default=0.0)
            ),
            "missing_period_count": int(_safe_float(summary_row.get("missing_period_count"), default=0.0)),
            "low_coverage_bin_count": int(
                _safe_float(summary_row.get("low_coverage_bin_count"), default=0.0)
            ),
            "expected_trend": _coalesce_text(
                summary_row.get("expected_trend"),
                getattr(child_binner, "monotonic", None),
            ),
            "alert_flags": _coalesce_text(summary_row.get("alert_flags")),
            "objective_source": objective_source,
            "score_strategy": _coalesce_text(
                objective_summary.get("score_strategy"),
                getattr(binner, "score_strategy", None),
                "standard",
            ),
            "objective_direction": _coalesce_text(
                objective_summary.get("objective_direction"),
                objective_config.get("objective_direction"),
                "maximize",
            ),
            "objective_score": _safe_float(objective_summary.get("score"), default=np.nan),
            "objective_preference_score": _safe_float(
                objective_summary.get("comparison_score"),
                default=np.nan,
            ),
            "objective_base_score": _safe_float(objective_summary.get("base_score"), default=np.nan),
            "objective_total_penalty": _safe_float(
                objective_summary.get("total_penalty"),
                default=np.nan,
            ),
            "objective_normalization_strategy": _coalesce_text(
                objective_config.get("normalization_strategy"),
                getattr(binner, "normalization_strategy", None),
            ),
            "woe_shrinkage_strength": _safe_float(
                objective_config.get("woe_shrinkage_strength"),
                default=getattr(binner, "woe_shrinkage_strength", np.nan),
            ),
            "missing_policy": getattr(binner, "missing_policy_", getattr(binner, "missing_policy", "standard")),
            "effective_missing_policy": getattr(
                binner,
                "effective_missing_policy_",
                getattr(binner, "missing_policy_", getattr(binner, "missing_policy", "standard")),
            ),
            "missing_merge_criterion": getattr(
                binner,
                "missing_merge_criterion_",
                getattr(binner, "missing_merge_criterion", None),
            ),
            "missing_merge_fallback": getattr(
                binner,
                "missing_merge_fallback_",
                getattr(binner, "missing_merge_fallback", None),
            ),
            "missing_merge_action": missing_decision_row.get("action"),
            "missing_merge_status": missing_decision_row.get("status"),
            "missing_merged_into": missing_decision_row.get("selected_bin_label"),
            "missing_original_n": missing_decision_row.get("n_missing_fit"),
            "missing_original_event_rate": missing_decision_row.get("event_rate_missing_fit"),
            "missing_original_woe": missing_decision_row.get(
                "missing_woe",
                missing_decision_row.get("woe_missing_fit"),
            ),
            "missing_selected_bin_woe": missing_decision_row.get("selected_bin_woe"),
            "missing_merge_distance_metric": missing_decision_row.get("distance_metric"),
            "missing_merge_distance": missing_decision_row.get("distance"),
            "missing_merge_distance_event_rate": missing_decision_row.get("distance_event_rate"),
            "missing_merge_distance_woe": missing_decision_row.get("distance_woe"),
        }

        for column in BASE_COMPONENT_COLUMNS:
            row[column] = _safe_float(base_components.get(column), default=0.0)
        for column in GENERALIZATION_BASE_COMPONENT_COLUMNS:
            row[column] = _safe_float(base_components.get(column), default=0.0)
        for column in PENALTY_COLUMNS:
            row[column] = _safe_float(penalties.get(column), default=0.0)
        for column in GENERALIZATION_PENALTY_COLUMNS:
            row[column] = _safe_float(penalties.get(column), default=0.0)

        if not np.isfinite(row["objective_preference_score"]):
            row["objective_preference_score"] = _objective_preference_score(row)

        for key, value in components.items():
            row[f"objective_raw_{key}"] = _safe_float(value, default=np.nan)
        for key, value in normalized_components.items():
            row[f"objective_norm_{key}"] = _safe_float(value, default=np.nan)
        for key, value in objective_summary.get("weights", {}).items():
            row[f"objective_weight_{key}"] = _safe_float(value, default=np.nan)

        row["key_drivers"] = _top_items(base_components)
        row["key_penalties"] = _top_items(penalties)
        row["selection_basis"] = _selection_basis(base_components)
        row["rationale_summary"] = _build_rationale_summary(row)
        rows.append(row)

    report = pd.DataFrame(rows).sort_values(["variable", "candidate_name"]).reset_index(drop=True)
    report.attrs["time_col"] = time_col
    report.attrs["dataset"] = dataset_name
    if collected_objective_summaries:
        binner.objective_summaries_ = collected_objective_summaries
        if len(collected_objective_summaries) == 1:
            binner.objective_summary_ = next(iter(collected_objective_summaries.values()))
    binner._variable_audit_report_ = report
    return report


def build_candidate_profile_report(candidate_reports: pd.DataFrame) -> pd.DataFrame:
    """
    Compare candidate reports through three conceptual lenses:
    static discrimination, temporal stability, and balanced objective score.
    """
    if candidate_reports.empty:
        return pd.DataFrame()

    df = candidate_reports.copy()
    score_columns = (
        [
        "objective_score",
        "objective_preference_score",
        "objective_total_penalty",
        "coverage_ratio_mean",
        "coverage_ratio_min",
        "rare_bin_count",
        "ranking_reversal_period_count",
        ]
        + BASE_COMPONENT_COLUMNS
        + GENERALIZATION_BASE_COMPONENT_COLUMNS
        + PENALTY_COLUMNS
        + GENERALIZATION_PENALTY_COLUMNS
    )
    for column in score_columns:
        if column not in df.columns:
            df[column] = 0.0
        df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0.0)

    if "objective_direction" not in df.columns:
        df["objective_direction"] = "maximize"
    df["objective_direction"] = df["objective_direction"].fillna("maximize")
    if "objective_preference_score" not in df.columns or (df["objective_preference_score"] == 0).all():
        df["objective_preference_score"] = df.apply(_objective_preference_score, axis=1)
    else:
        missing_pref = ~np.isfinite(df["objective_preference_score"])
        if missing_pref.any():
            df.loc[missing_pref, "objective_preference_score"] = df.loc[missing_pref].apply(
                _objective_preference_score,
                axis=1,
            )

    df["static_profile_score"] = (
        df["iv_component"] + df["ks_component"] - df["iv_shortfall_penalty"]
    )
    df["temporal_profile_score"] = (
        df["separability_component"]
        + df["separation_reward_component"]
        + df["temporal_score_component"]
        - df[TEMPORAL_PROFILE_PENALTIES].sum(axis=1)
    )
    df["balanced_profile_score"] = df["objective_preference_score"]

    group_cols = ["variable"]
    if "dataset" in df.columns and df["dataset"].notna().any():
        group_cols = ["dataset"] + group_cols

    for score_col, prefix in (
        ("static_profile_score", "static"),
        ("temporal_profile_score", "temporal"),
        ("balanced_profile_score", "balanced"),
    ):
        df[f"{prefix}_rank"] = (
            df.groupby(group_cols, dropna=False)[score_col]
            .rank(method="dense", ascending=False)
            .astype(int)
        )

    roles = []
    for _, row in df.iterrows():
        role_parts = []
        if row["static_rank"] == 1:
            role_parts.append("static_leader")
        if row["temporal_rank"] == 1:
            role_parts.append("temporal_leader")
        if row["balanced_rank"] == 1:
            role_parts.append("balanced_winner")
        roles.append(";".join(role_parts) if role_parts else "contender")
    df["candidate_role"] = roles
    return df


def _winner_advantage_summary(winner: pd.Series, runner_up: pd.Series | None) -> str:
    if runner_up is None:
        return _coalesce_text(winner.get("rationale_summary"))

    advantages = []
    comparisons = [
        ("maior IV", _safe_float(winner.get("iv"), default=np.nan) - _safe_float(runner_up.get("iv"), default=np.nan)),
        (
            "maior score temporal",
            _safe_float(winner.get("temporal_score"), default=np.nan)
            - _safe_float(runner_up.get("temporal_score"), default=np.nan),
        ),
        (
            "menor penalizacao total",
            _safe_float(runner_up.get("objective_total_penalty"), default=np.nan)
            - _safe_float(winner.get("objective_total_penalty"), default=np.nan),
        ),
        (
            "melhor cobertura minima",
            _safe_float(winner.get("coverage_ratio_min"), default=np.nan)
            - _safe_float(runner_up.get("coverage_ratio_min"), default=np.nan),
        ),
        (
            "menos bins raros",
            _safe_float(runner_up.get("rare_bin_count"), default=np.nan)
            - _safe_float(winner.get("rare_bin_count"), default=np.nan),
        ),
        (
            "menos reversoes de ranking",
            _safe_float(runner_up.get("ranking_reversal_period_count"), default=np.nan)
            - _safe_float(winner.get("ranking_reversal_period_count"), default=np.nan),
        ),
    ]

    for label, delta in comparisons:
        if np.isfinite(delta) and delta > 0:
            advantages.append((label, float(delta)))

    if not advantages:
        return _coalesce_text(winner.get("rationale_summary"))

    advantages.sort(key=lambda item: item[1], reverse=True)
    labels = ", ".join(label for label, _ in advantages[:2])
    runner_name = _coalesce_text(runner_up.get("candidate_name"), "o concorrente")
    return f"Selecionado como melhor equilibrio frente a {runner_name} por {labels}."


def build_candidate_winner_report(candidate_profiles: pd.DataFrame) -> pd.DataFrame:
    """
    Summarize which candidate wins under each conceptual profile and why.
    """
    if candidate_profiles.empty:
        return pd.DataFrame()

    group_cols = ["variable"]
    if "dataset" in candidate_profiles.columns and candidate_profiles["dataset"].notna().any():
        group_cols = ["dataset"] + group_cols

    records = []
    for group_key, group in candidate_profiles.groupby(group_cols, dropna=False):
        if isinstance(group_key, tuple):
            group_info = dict(zip(group_cols, group_key, strict=False))
        else:
            group_info = {group_cols[0]: group_key}

        static_winner = group.sort_values(
            ["static_profile_score", "iv", "ks"],
            ascending=False,
        ).iloc[0]
        temporal_winner = group.sort_values(
            ["temporal_profile_score", "temporal_score", "coverage_ratio_min"],
            ascending=False,
        ).iloc[0]
        balanced_group = group.sort_values(
            ["balanced_profile_score", "temporal_profile_score", "static_profile_score"],
            ascending=False,
        ).reset_index(drop=True)
        balanced_winner = balanced_group.iloc[0]
        runner_up = balanced_group.iloc[1] if len(balanced_group) > 1 else None

        records.append(
            {
                **group_info,
                "best_static_candidate": static_winner["candidate_name"],
                "best_temporal_candidate": temporal_winner["candidate_name"],
                "best_balanced_candidate": balanced_winner["candidate_name"],
                "selected_candidate": balanced_winner["candidate_name"],
                "selected_strategy": balanced_winner["selected_strategy"],
                "runner_up_candidate": runner_up["candidate_name"] if runner_up is not None else None,
                "winner_margin": (
                    _safe_float(balanced_winner["balanced_profile_score"])
                    - _safe_float(runner_up["balanced_profile_score"])
                    if runner_up is not None
                    else np.nan
                ),
                "selected_basis": balanced_winner["selection_basis"],
                "winner_key_drivers": balanced_winner["key_drivers"],
                "winner_key_penalties": balanced_winner["key_penalties"],
                "winner_alert_flags": balanced_winner["alert_flags"],
                "winner_rationale": _winner_advantage_summary(balanced_winner, runner_up),
            }
        )

    return pd.DataFrame(records).sort_values(group_cols).reset_index(drop=True)


def _resolve_variable_audit_report(binner: Binner) -> pd.DataFrame | None:
    audit = getattr(binner, "_variable_audit_report_", None)
    if audit is not None:
        return audit

    try:
        audit = build_variable_audit_report(binner)
    except (RuntimeError, ValueError, KeyError):
        return None
    return audit if not audit.empty else None


def build_binner_metadata(
    binner: Binner,
    *,
    time_col: str | None = None,
) -> dict[str, Any]:
    objective_config = getattr(binner, "objective_config_", None)
    if objective_config is None and hasattr(binner, "_resolved_objective_kwargs"):
        try:
            objective_config = resolve_objective_config(binner._resolved_objective_kwargs())
        except Exception:  # pragma: no cover - metadata should be best effort
            objective_config = None

    objective_direction = None
    normalization_strategy = getattr(binner, "normalization_strategy", None)
    woe_shrinkage_strength = getattr(binner, "woe_shrinkage_strength", None)
    score_weights_input = (
        dict(getattr(binner, "score_weights", {}) or {})
        if getattr(binner, "score_weights", None) is not None
        else {}
    )
    score_weights = {}
    if isinstance(objective_config, dict):
        objective_direction = objective_config.get("objective_direction")
        normalization_strategy = objective_config.get(
            "normalization_strategy",
            normalization_strategy,
        )
        woe_shrinkage_strength = objective_config.get(
            "woe_shrinkage_strength",
            woe_shrinkage_strength,
        )
        score_weights_input = dict(objective_config.get("weights_input", {}) or score_weights_input)
        score_weights = dict(objective_config.get("weights", {}) or {})

    metadata = {
        "riskbands_version": resolve_version(),
        "strategy": getattr(binner, "strategy", None),
        "score_strategy": resolve_score_strategy(score_strategy=getattr(binner, "score_strategy", None)),
        "missing_policy": getattr(binner, "missing_policy_", getattr(binner, "missing_policy", "standard")),
        "effective_missing_policy": getattr(
            binner,
            "effective_missing_policy_",
            getattr(binner, "missing_policy_", getattr(binner, "missing_policy", "standard")),
        ),
        "missing_merge_criterion": getattr(
            binner,
            "missing_merge_criterion_",
            getattr(binner, "missing_merge_criterion", None),
        ),
        "missing_merge_fallback": getattr(
            binner,
            "missing_merge_fallback_",
            getattr(binner, "missing_merge_fallback", None),
        ),
        "objective_direction": objective_direction,
        "normalization_strategy": normalization_strategy,
        "woe_shrinkage_strength": (
            _safe_float(woe_shrinkage_strength, default=np.nan)
            if woe_shrinkage_strength is not None
            else None
        ),
        "score_weights_input": score_weights_input,
        "score_weights": score_weights,
        "score_weights_profile": _format_key_value_profile(score_weights),
        "target_name": getattr(binner, "target_name_", None),
        "time_col": time_col if time_col is not None else getattr(binner, "time_col", None),
        "features": list(getattr(binner, "feature_names_in_", [])),
        "selected_columns": list(getattr(binner, "selected_columns_", []) or []),
        "n_features": int(getattr(binner, "n_features_in_", 0)),
        "input_type": getattr(binner, "input_type_", None),
        "iv_total": _safe_float(getattr(binner, "iv_", np.nan), default=np.nan),
    }
    min_n_bins_metadata = getattr(binner, "min_n_bins_metadata_", None)
    if min_n_bins_metadata is not None:
        metadata["min_n_bins"] = getattr(binner, "min_n_bins", None)
        metadata["min_n_bins_metadata"] = _json_safe(min_n_bins_metadata)
    sampling_metadata = getattr(binner, "sampling_metadata_", None)
    if sampling_metadata is not None:
        metadata["sampling_metadata"] = _json_safe(sampling_metadata)
    backend_metadata = getattr(binner, "backend_metadata_", None)
    if backend_metadata is not None:
        metadata["backend_metadata"] = _json_safe(backend_metadata)
    reference_profile_source = getattr(binner, "reference_profile_source_", None)
    if reference_profile_source is not None:
        metadata["reference_profile_source"] = reference_profile_source
    if objective_config is not None:
        metadata["objective_config"] = _json_safe(objective_config)
    return _json_safe(metadata)


def _collect_optional_bundle_profile_fields(binner: Binner) -> dict[str, Any]:
    fields = {}
    for field in OPTIONAL_BUNDLE_PROFILE_FIELDS:
        value = getattr(binner, f"{field}_", None)
        if value is not None:
            fields[field] = _json_safe(value)
    return fields


def _normalize_loaded_missing_policy(value: Any) -> str:
    if value is None:
        return "standard"
    text = str(value)
    if text == "legacy":
        return "standard"
    if text in {"standard", "separate_bin", "forbid", "merge"}:
        return text
    return text


def _normalize_loaded_score_strategy(value: Any) -> Any:
    if value is None:
        return value
    try:
        return resolve_score_strategy(score_strategy=str(value))
    except ValueError:
        return value


def _normalize_loaded_bundle_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    normalized.setdefault(
        "bundle_schema_version",
        str(normalized.get("artifact_version") or LEGACY_BUNDLE_SCHEMA_VERSION),
    )
    metadata = normalized.get("metadata")
    if isinstance(metadata, dict):
        metadata = dict(metadata)
        metadata["score_strategy"] = _normalize_loaded_score_strategy(
            metadata.get("score_strategy")
        )
        metadata["missing_policy"] = _normalize_loaded_missing_policy(
            metadata.get("missing_policy")
        )
        metadata["effective_missing_policy"] = _normalize_loaded_missing_policy(
            metadata.get("effective_missing_policy", metadata.get("missing_policy"))
        )
        normalized["metadata"] = metadata
    if "riskbands_version" not in normalized and isinstance(metadata, dict):
        normalized["riskbands_version"] = metadata.get("riskbands_version")
    for field in OPTIONAL_BUNDLE_PROFILE_FIELDS:
        normalized.setdefault(field, None)
    normalized["missing_policy"] = _normalize_loaded_missing_policy(
        normalized.get("missing_policy")
    )
    normalized["effective_missing_policy"] = _normalize_loaded_missing_policy(
        normalized.get("effective_missing_policy", normalized.get("missing_policy"))
    )
    if isinstance(metadata, dict):
        normalized["metadata"]["missing_policy"] = normalized["missing_policy"]
        normalized["metadata"]["effective_missing_policy"] = normalized["effective_missing_policy"]
    if normalized.get("reference_profile") is None:
        if normalized.get("source_profile") is not None:
            normalized["reference_profile"] = normalized["source_profile"]
            normalized["reference_profile_source"] = "source_profile"
        elif normalized.get("fit_profile") is not None:
            normalized["reference_profile"] = normalized["fit_profile"]
            normalized["reference_profile_source"] = "fit_profile"
    if normalized.get("reference_profile_source") is None:
        normalized["reference_profile_source"] = (
            "missing" if normalized.get("reference_profile") is None else "fit_profile"
        )
    return normalized


def load_bundle_metadata(path: PathLike) -> dict[str, Any]:
    """Load and normalize a RiskBands bundle manifest or metadata JSON file."""
    target = Path(path)
    metadata_path = target / "metadata.json" if target.is_dir() else target
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("RiskBands bundle metadata must be a JSON object.")
    return _normalize_loaded_bundle_payload(payload)


def load_bundle(path: PathLike) -> dict[str, Any]:
    """Load a RiskBands audit bundle directory with normalized manifest and binnings."""
    target = Path(path)
    if not target.is_dir():
        raise ValueError("`load_bundle` expects a RiskBands bundle directory.")

    manifest = load_bundle_metadata(target)
    binnings_path = target / "binnings.json"
    binnings = None
    if binnings_path.exists():
        binnings_payload = json.loads(binnings_path.read_text(encoding="utf-8"))
        if not isinstance(binnings_payload, dict):
            raise ValueError("RiskBands binnings artifact must be a JSON object.")
        binnings = _normalize_loaded_bundle_payload(binnings_payload)

    return {
        "manifest": manifest,
        "binnings": binnings,
        "bundle_schema_version": manifest.get("bundle_schema_version"),
        "riskbands_version": manifest.get("riskbands_version"),
        "reference_profile": manifest.get("reference_profile"),
        "reference_profile_source": manifest.get("reference_profile_source"),
        "fit_profile": manifest.get("fit_profile"),
        "source_profile": manifest.get("source_profile"),
        "fit_validation_report": manifest.get("fit_validation_report"),
        "transform_validation_report": manifest.get("transform_validation_report"),
        "validation_report": manifest.get("validation_report"),
        "missing_policy": manifest.get("missing_policy"),
        "effective_missing_policy": manifest.get("effective_missing_policy"),
        "missing_merge_criterion": manifest.get("missing_merge_criterion"),
        "missing_merge_fallback": manifest.get("missing_merge_fallback"),
        "missing_profile": manifest.get("missing_profile"),
        "missing_decision_log": manifest.get("missing_decision_log"),
        "missing_merge_candidates": manifest.get("missing_merge_candidates"),
        "missing_merge_map": manifest.get("missing_merge_map"),
        "missing_transform_fallback_log": manifest.get("missing_transform_fallback_log"),
    }


def _resolve_optional_table(
    binner: Binner,
    *,
    kind: str,
) -> pd.DataFrame:
    try:
        return binner.diagnostics(kind=kind)
    except Exception:
        return pd.DataFrame()


def build_binnings_json_artifact(binner: Binner) -> dict[str, Any]:
    metadata = build_binner_metadata(binner)
    generated_at = datetime.now(timezone.utc).isoformat()
    binning_table = binner.binning_table()
    summary = binner.summary()
    score_table = binner.score_table()
    audit_table = binner.audit_table()
    diagnostics = _resolve_optional_table(binner, kind="bin")
    temporal_summary = _resolve_optional_table(binner, kind="variable")

    features = {}
    ordered_features = metadata.get("features") or (
        binning_table["variable"].drop_duplicates().tolist()
        if not binning_table.empty and "variable" in binning_table.columns
        else []
    )
    for feature in ordered_features:
        feature_payload = {
            "binning_table": _json_ready_records(binner.binning_table(column=feature)),
        }
        if not summary.empty and "variable" in summary.columns:
            feature_summary = summary.loc[summary["variable"] == feature]
            if not feature_summary.empty:
                feature_payload["summary"] = _json_safe(feature_summary.iloc[0].to_dict())
        if not score_table.empty and "variable" in score_table.columns:
            feature_score = score_table.loc[score_table["variable"] == feature]
            if not feature_score.empty:
                feature_payload["score_details"] = _json_safe(feature_score.iloc[0].to_dict())
        if not audit_table.empty and "variable" in audit_table.columns:
            feature_audit = audit_table.loc[audit_table["variable"] == feature]
            if not feature_audit.empty:
                feature_payload["audit"] = _json_safe(feature_audit.iloc[0].to_dict())
        if not temporal_summary.empty and "variable" in temporal_summary.columns:
            feature_temporal = temporal_summary.loc[temporal_summary["variable"] == feature]
            if not feature_temporal.empty:
                feature_payload["temporal_summary"] = _json_safe(feature_temporal.iloc[0].to_dict())
        if not diagnostics.empty and "variable" in diagnostics.columns:
            feature_diag = diagnostics.loc[diagnostics["variable"] == feature]
            if not feature_diag.empty:
                feature_payload["diagnostics"] = _json_ready_records(feature_diag)
        features[str(feature)] = feature_payload

    return {
        "artifact_type": "riskbands_binning_bundle",
        "artifact_version": "1.0",
        "bundle_schema_version": BUNDLE_SCHEMA_VERSION,
        "riskbands_version": resolve_version(),
        "generated_at": generated_at,
        "metadata": metadata,
        "features": features,
        **_collect_optional_bundle_profile_fields(binner),
    }


def export_binnings_json(binner: Binner, path: PathLike) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = build_binnings_json_artifact(binner)
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return target


def _write_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def _try_write_parquet(df: pd.DataFrame, path: Path) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(path, index=False)
        return True
    except Exception:
        return False


def export_binner_bundle(
    binner: Binner,
    path: PathLike,
    *,
    include_audit_report: bool = True,
) -> Path:
    target_dir = Path(path)
    target_dir.mkdir(parents=True, exist_ok=True)

    binnings_path = export_binnings_json(binner, target_dir / "binnings.json")
    metadata = build_binner_metadata(binner)
    summary = binner.summary()
    score_details = binner.score_details()
    score_table = binner.score_table()
    audit_table = binner.audit_table()
    report = binner.report()
    diagnostics = _resolve_optional_table(binner, kind="bin")
    diagnostics_variable = _resolve_optional_table(binner, kind="variable")
    missing_profile = getattr(binner, "missing_profile_", pd.DataFrame())
    missing_decision_log = getattr(binner, "missing_decision_log_", pd.DataFrame())
    missing_merge_candidates = getattr(binner, "missing_merge_candidates_", pd.DataFrame())
    missing_transform_fallback_log = getattr(
        binner,
        "missing_transform_fallback_log_",
        pd.DataFrame(),
    )

    _write_csv(summary, target_dir / "summary.csv")
    _write_csv(score_details, target_dir / "score_details.csv")
    _write_csv(score_table, target_dir / "score_table.csv")
    _write_csv(audit_table, target_dir / "audit_table.csv")
    if not diagnostics.empty:
        _write_csv(diagnostics, target_dir / "diagnostics.csv")
    if not diagnostics_variable.empty:
        _write_csv(diagnostics_variable, target_dir / "diagnostics_variable.csv")
    if missing_profile is not None and not missing_profile.empty:
        _write_csv(missing_profile, target_dir / "missing_profile.csv")
    if missing_decision_log is not None and not missing_decision_log.empty:
        _write_csv(missing_decision_log, target_dir / "missing_decision_log.csv")
    if missing_merge_candidates is not None and not missing_merge_candidates.empty:
        _write_csv(missing_merge_candidates, target_dir / "missing_merge_candidates.csv")
    if missing_transform_fallback_log is not None and not missing_transform_fallback_log.empty:
        _write_csv(missing_transform_fallback_log, target_dir / "missing_transform_fallback_log.csv")
    _write_csv(report, target_dir / "report.csv")

    feature_dir = target_dir / "feature_tables"
    feature_dir.mkdir(parents=True, exist_ok=True)
    feature_artifacts = {}
    used_feature_table_names: set[str] = set()
    for feature in metadata.get("features", []):
        safe_stem = _safe_artifact_name(feature)
        feature_filename = f"{_unique_artifact_name(safe_stem, used_feature_table_names)}.csv"
        feature_path = feature_dir / feature_filename
        feature_path = _ensure_path_inside(target_dir, feature_path)
        feature_path = _ensure_path_inside(feature_dir, feature_path)
        if feature_path.resolve().parent != feature_dir.resolve():
            raise ValueError(f"Refusing to write feature table outside feature_tables: {feature_path}")
        _write_csv(binner.binning_table(column=feature), feature_path)
        feature_artifacts[str(feature)] = feature_path.relative_to(target_dir).as_posix()

    written_optional = []
    skipped_optional = []
    if _try_write_parquet(report, target_dir / "report.parquet"):
        written_optional.append("report.parquet")
    else:
        skipped_optional.append("report.parquet")
    if not diagnostics.empty:
        if _try_write_parquet(diagnostics, target_dir / "diagnostics.parquet"):
            written_optional.append("diagnostics.parquet")
        else:
            skipped_optional.append("diagnostics.parquet")

    manifest = {
        "artifact_type": "riskbands_audit_bundle",
        "artifact_version": "1.0",
        "bundle_schema_version": BUNDLE_SCHEMA_VERSION,
        "riskbands_version": resolve_version(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "metadata": metadata,
        "artifacts": {
            "binnings_json": str(binnings_path.relative_to(target_dir)),
            "summary_csv": "summary.csv",
            "score_details_csv": "score_details.csv",
            "score_table_csv": "score_table.csv",
            "audit_table_csv": "audit_table.csv",
            "report_csv": "report.csv",
            "diagnostics_csv": "diagnostics.csv" if not diagnostics.empty else None,
            "diagnostics_variable_csv": (
                "diagnostics_variable.csv" if not diagnostics_variable.empty else None
            ),
            "missing_profile_csv": (
                "missing_profile.csv"
                if missing_profile is not None and not missing_profile.empty
                else None
            ),
            "missing_decision_log_csv": (
                "missing_decision_log.csv"
                if missing_decision_log is not None and not missing_decision_log.empty
                else None
            ),
            "missing_merge_candidates_csv": (
                "missing_merge_candidates.csv"
                if missing_merge_candidates is not None and not missing_merge_candidates.empty
                else None
            ),
            "missing_transform_fallback_log_csv": (
                "missing_transform_fallback_log.csv"
                if missing_transform_fallback_log is not None and not missing_transform_fallback_log.empty
                else None
            ),
            "audit_report_html": "audit_report.html" if include_audit_report else None,
            "feature_tables": feature_artifacts,
            "optional_parquet": written_optional,
        },
        "skipped_optional_artifacts": skipped_optional,
        **_collect_optional_bundle_profile_fields(binner),
    }
    (target_dir / "metadata.json").write_text(
        json.dumps(_json_safe(manifest), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    if include_audit_report:
        from .audit_report import export_audit_report_html

        export_audit_report_html(
            binner,
            target_dir / "audit_report.html",
            bundle_path=target_dir,
        )
    return target_dir


# ------------------------------------------------------------------ #
def save_binner_report(binner: Binner, path: PathLike) -> None:
    """
    Save bin table, summary metrics and optional temporal diagnostics.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.suffix.lower() == ".json":
        _save_json(binner, p)
    else:
        _save_excel(binner, p.with_suffix(".xlsx"))


def _resolve_excel_writer_engine() -> str:
    for engine in ("openpyxl", "xlsxwriter"):
        if find_spec(engine) is not None:
            return engine
    raise ImportError(
        "Excel export requires an XLSX writer engine. "
        "Install `openpyxl` or `xlsxwriter` to use save_report(..., '.xlsx')."
    )


def _save_excel(binner: Binner, path: Path) -> None:
    bin_summary = _require_bin_summary(binner)
    with pd.ExcelWriter(path, engine=_resolve_excel_writer_engine()) as writer:
        bin_summary.to_excel(writer, sheet_name="bin_table", index=False)
        meta = pd.DataFrame(
            {
                "metric": ["IV", "n_bins", "PSI_over_time", "n_variables"],
                "value": [
                    binner.iv_,
                    len(bin_summary),
                    bin_summary.attrs.get("psi_over_time"),
                    bin_summary["variable"].nunique(),
                ],
            }
        )
        meta.to_excel(writer, sheet_name="metrics", index=False)

        pivot = getattr(binner, "_pivot_", None)
        if pivot is not None:
            pivot.to_excel(writer, sheet_name="pivot_event_rate")

        diagnostics = getattr(binner, "_temporal_bin_diagnostics_", None)
        if diagnostics is not None:
            diagnostics.to_excel(writer, sheet_name="temporal_diag", index=False)

        summary = getattr(binner, "_temporal_variable_summary_", None)
        if summary is not None:
            summary.to_excel(writer, sheet_name="temporal_summary", index=False)

        audit = _resolve_variable_audit_report(binner)
        if audit is not None:
            audit.to_excel(writer, sheet_name="variable_audit", index=False)
        missing_profile = getattr(binner, "missing_profile_", None)
        if missing_profile is not None and not missing_profile.empty:
            missing_profile.to_excel(writer, sheet_name="missing_profile", index=False)
        missing_decision_log = getattr(binner, "missing_decision_log_", None)
        if missing_decision_log is not None and not missing_decision_log.empty:
            missing_decision_log.to_excel(writer, sheet_name="missing_decisions", index=False)
        missing_merge_candidates = getattr(binner, "missing_merge_candidates_", None)
        if missing_merge_candidates is not None and not missing_merge_candidates.empty:
            missing_merge_candidates.to_excel(writer, sheet_name="missing_merge_candidates", index=False)
        missing_transform_log = getattr(binner, "missing_transform_fallback_log_", None)
        if missing_transform_log is not None and not missing_transform_log.empty:
            missing_transform_log.to_excel(writer, sheet_name="missing_transform_log", index=False)


# ------------------------------------------------------------------ #
def _save_json(binner: Binner, path: Path) -> None:
    bin_summary = _require_bin_summary(binner)
    info = {
        "iv": binner.iv_,
        "iv_by_variable": getattr(binner, "iv_by_variable_", pd.Series(dtype=float)).to_dict(),
        "n_bins": len(bin_summary),
        "psi_over_time": bin_summary.attrs.get("psi_over_time"),
        "bin_table": _json_ready_records(bin_summary),
        "metadata": build_binner_metadata(binner),
        "score_table": _json_ready_records(binner.score_table()) if hasattr(binner, "score_table") else [],
    }
    if getattr(binner, "objective_config_", None) is not None:
        info["objective_config"] = _json_safe(binner.objective_config_)
    if getattr(binner, "objective_summary_", None) is not None:
        info["objective_summary"] = _json_safe(binner.objective_summary_)
    if getattr(binner, "objective_summaries_", None) is not None:
        info["objective_summaries"] = _json_safe(binner.objective_summaries_)
    if getattr(binner, "missing_policy_", None) is not None:
        info["missing_policy"] = _json_safe(binner.missing_policy_)
    if getattr(binner, "effective_missing_policy_", None) is not None:
        info["effective_missing_policy"] = _json_safe(binner.effective_missing_policy_)
    if getattr(binner, "missing_merge_criterion_", None) is not None:
        info["missing_merge_criterion"] = _json_safe(binner.missing_merge_criterion_)
    if getattr(binner, "missing_merge_fallback_", None) is not None:
        info["missing_merge_fallback"] = _json_safe(binner.missing_merge_fallback_)
    if getattr(binner, "missing_profile_", None) is not None:
        info["missing_profile"] = _json_safe(binner.missing_profile_)
    if getattr(binner, "missing_decision_log_", None) is not None:
        info["missing_decision_log"] = _json_safe(binner.missing_decision_log_)
    if getattr(binner, "missing_merge_candidates_", None) is not None:
        info["missing_merge_candidates"] = _json_safe(binner.missing_merge_candidates_)
    if getattr(binner, "missing_merge_map_", None) is not None:
        info["missing_merge_map"] = _json_safe(binner.missing_merge_map_)
    if getattr(binner, "missing_transform_fallback_log_", None) is not None:
        info["missing_transform_fallback_log"] = _json_safe(binner.missing_transform_fallback_log_)
    pivot = getattr(binner, "_pivot_", None)
    if pivot is not None:
        info["pivot_event_rate"] = _json_ready_records(pivot.reset_index())
    diagnostics = getattr(binner, "_temporal_bin_diagnostics_", None)
    if diagnostics is not None:
        info["temporal_bin_diagnostics"] = _json_ready_records(diagnostics)
    summary = getattr(binner, "_temporal_variable_summary_", None)
    if summary is not None:
        info["temporal_variable_summary"] = _json_ready_records(summary)
    audit = _resolve_variable_audit_report(binner)
    if audit is not None:
        info["variable_audit_report"] = _json_ready_records(audit)
    info["binnings_artifact"] = build_binnings_json_artifact(binner)
    path.write_text(json.dumps(_json_safe(info), indent=2, ensure_ascii=False), encoding="utf-8")
