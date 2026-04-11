"""Auditable report generation for RiskBands objects."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Union

import numpy as np
import pandas as pd

from .binning_engine import Binner
from .optuna_optimizer import score_objective_components
from .temporal_stability import event_rate_by_time, ks_over_time, temporal_separability_score

PathLike = Union[str, Path]

BASE_COMPONENT_COLUMNS = [
    "separability_component",
    "iv_component",
    "ks_component",
    "temporal_score_component",
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

TEMPORAL_PROFILE_PENALTIES = [
    "rare_bin_penalty",
    "coverage_gap_penalty",
    "event_rate_volatility_penalty",
    "woe_volatility_penalty",
    "share_volatility_penalty",
    "monotonic_break_penalty",
    "ranking_reversal_penalty",
    "temporal_shortfall_penalty",
]


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
    return clean.to_dict(orient="records")


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
    time_col: str | None,
    iv_value: float | None,
    summary_row: dict[str, Any] | None,
    objective_kwargs: dict[str, Any] | None,
) -> tuple[dict[str, Any], str]:
    summaries = getattr(binner, "objective_summaries_", None)
    if isinstance(summaries, dict) and summaries.get(variable):
        return summaries[variable], "stored_multi_feature"

    summary = getattr(binner, "objective_summary_", None)
    if summary:
        return summary, "stored_single_feature"

    if X is None or y is None:
        return {}, "unavailable"

    child_binner = _resolve_child_binner(binner, variable)
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

    derived = score_objective_components(components, objective_kwargs=objective_kwargs)
    return derived, "derived_default_objective"


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
    rows = []

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
            time_col=time_col,
            iv_value=_safe_float(iv_by_variable.get(variable), default=0.0),
            summary_row=summary_row,
            objective_kwargs=objective_kwargs,
        )
        components = objective_summary.get("components", {})
        base_components = objective_summary.get("base_components", {})
        penalties = objective_summary.get("penalties", {})

        dataset_value = _coalesce_text(
            summary_row.get("dataset"),
            dataset_name,
            diagnostics.attrs.get("dataset") if diagnostics is not None else None,
        )

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
            "separability": _safe_float(components.get("separability"), default=np.nan),
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
            "objective_score": _safe_float(objective_summary.get("score"), default=np.nan),
            "objective_base_score": _safe_float(objective_summary.get("base_score"), default=np.nan),
            "objective_total_penalty": _safe_float(
                objective_summary.get("total_penalty"),
                default=np.nan,
            ),
        }

        for column in BASE_COMPONENT_COLUMNS:
            row[column] = _safe_float(base_components.get(column), default=0.0)
        for column in PENALTY_COLUMNS:
            row[column] = _safe_float(penalties.get(column), default=0.0)

        row["key_drivers"] = _top_items(base_components)
        row["key_penalties"] = _top_items(penalties)
        row["selection_basis"] = _selection_basis(base_components)
        row["rationale_summary"] = _build_rationale_summary(row)
        rows.append(row)

    report = pd.DataFrame(rows).sort_values(["variable", "candidate_name"]).reset_index(drop=True)
    report.attrs["time_col"] = time_col
    report.attrs["dataset"] = dataset_name
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
    for column in [
        "objective_score",
        "objective_total_penalty",
        "coverage_ratio_mean",
        "coverage_ratio_min",
        "rare_bin_count",
        "ranking_reversal_period_count",
    ] + BASE_COMPONENT_COLUMNS + PENALTY_COLUMNS:
        if column not in df.columns:
            df[column] = 0.0
        df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0.0)

    df["static_profile_score"] = (
        df["iv_component"] + df["ks_component"] - df["iv_shortfall_penalty"]
    )
    df["temporal_profile_score"] = (
        df["separability_component"]
        + df["temporal_score_component"]
        - df[TEMPORAL_PROFILE_PENALTIES].sum(axis=1)
    )
    df["balanced_profile_score"] = df["objective_score"]

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
            group_info = dict(zip(group_cols, group_key))
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


def _save_excel(binner: Binner, path: Path) -> None:
    bin_summary = _require_bin_summary(binner)
    with pd.ExcelWriter(path) as writer:
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


# ------------------------------------------------------------------ #
def _save_json(binner: Binner, path: Path) -> None:
    bin_summary = _require_bin_summary(binner)
    info = {
        "iv": binner.iv_,
        "iv_by_variable": getattr(binner, "iv_by_variable_", pd.Series(dtype=float)).to_dict(),
        "n_bins": len(bin_summary),
        "psi_over_time": bin_summary.attrs.get("psi_over_time"),
        "bin_table": _json_ready_records(bin_summary),
    }
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
    path.write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")


