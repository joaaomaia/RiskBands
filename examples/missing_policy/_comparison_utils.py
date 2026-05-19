"""Utilities for synthetic missing-policy comparison examples."""

from __future__ import annotations

from tempfile import TemporaryDirectory
from typing import Any

import numpy as np
import pandas as pd

from riskbands import RiskBands
from riskbands.reporting import load_bundle

POLICY_CONFIGS: tuple[dict[str, Any], ...] = (
    {"name": "standard", "kwargs": {"missing_policy": "standard"}},
    {"name": "separate_bin", "kwargs": {"missing_policy": "separate_bin"}},
    {
        "name": "merge_nearest_event_rate",
        "kwargs": {
            "missing_policy": "merge",
            "missing_merge_criterion": "nearest_event_rate",
            "missing_merge_fallback": "separate_bin",
        },
    },
    {
        "name": "merge_nearest_woe",
        "kwargs": {
            "missing_policy": "merge",
            "missing_merge_criterion": "nearest_woe",
            "missing_merge_fallback": "separate_bin",
        },
    },
    {"name": "forbid", "kwargs": {"missing_policy": "forbid"}},
)


def make_policy_comparison_frame() -> pd.DataFrame:
    """Build a deterministic credit-like single-feature frame with vintages."""

    rows: list[dict[str, Any]] = []
    vintages = ["2025Q1", "2025Q2", "2025Q3", "2025Q4"]
    regular_specs = [
        (420.0, 0.36),
        (520.0, 0.24),
        (620.0, 0.12),
        (720.0, 0.06),
    ]
    for vintage_idx, vintage in enumerate(vintages):
        drift = (vintage_idx - 1.5) * 0.015
        for score, base_rate in regular_specs:
            n = 24
            event_rate = min(max(base_rate + drift, 0.02), 0.95)
            events = int(round(n * event_rate))
            for row_idx in range(n):
                rows.append(
                    {
                        "score": score + (row_idx % 3) * 2.0,
                        "vintage": vintage,
                        "target": int(row_idx < events),
                    }
                )

        missing_n = 14
        missing_rate = min(max(0.23 + drift, 0.02), 0.95)
        missing_events = int(round(missing_n * missing_rate))
        for row_idx in range(missing_n):
            rows.append(
                {
                    "score": np.nan,
                    "vintage": vintage,
                    "target": int(row_idx < missing_events),
                }
            )

    return pd.DataFrame(rows)


def _first_record(frame: pd.DataFrame) -> dict[str, Any]:
    if frame is None or frame.empty:
        return {}
    return frame.iloc[0].to_dict()


def _bool_or_none(value: Any) -> bool | None:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    return bool(value)


def compute_time_stability_metric(
    source: pd.DataFrame,
    transformed: pd.DataFrame,
    *,
    feature: str,
    target: str,
    time_col: str | None,
) -> float | None:
    """Mean range of event rates across periods for transformed bins."""

    if time_col is None or time_col not in source.columns:
        return None
    tmp = pd.DataFrame(
        {
            "bin": transformed[feature].astype(str),
            "target": source[target].to_numpy(),
            "time": source[time_col].astype(str).to_numpy(),
        }
    )
    rates = tmp.groupby(["bin", "time"], dropna=False)["target"].mean().unstack("time")
    if rates.empty:
        return None
    return float((rates.max(axis=1) - rates.min(axis=1)).mean())


def summarize_policy_result(
    *,
    policy_name: str,
    binner: RiskBands | None,
    source: pd.DataFrame,
    transformed: pd.DataFrame | None,
    feature: str,
    target: str,
    time_col: str | None,
    error: str | None = None,
) -> dict[str, Any]:
    if binner is None:
        return {
            "policy": policy_name,
            "merge_criterion": None,
            "n_bins": None,
            "iv": None,
            "missing_event_rate": None,
            "missing_action": "error",
            "selected_bin": None,
            "distance": None,
            "candidate_count": 0,
            "fallback_used": None,
            "time_stability_metric": None,
            "bundle_export_possible": False,
            "error": error,
        }

    decision = _first_record(getattr(binner, "missing_decision_log_", pd.DataFrame()))
    profile = _first_record(getattr(binner, "missing_profile_", pd.DataFrame()))
    bundle_export_possible = False
    try:
        with TemporaryDirectory(prefix="riskbands_missing_policy_comparison_") as tmpdir:
            binner.export_bundle(tmpdir)
            loaded = load_bundle(tmpdir)
            bundle_export_possible = loaded["missing_policy"] == binner.missing_policy_
    except Exception:
        bundle_export_possible = False

    return {
        "policy": policy_name,
        "merge_criterion": getattr(binner, "missing_merge_criterion_", None),
        "n_bins": int(len(binner.bin_summary)),
        "iv": float(getattr(binner, "iv_by_variable_", pd.Series(dtype=float)).get(feature, np.nan)),
        "missing_event_rate": profile.get("event_rate_missing_fit"),
        "missing_action": decision.get("action"),
        "selected_bin": decision.get("selected_bin_label"),
        "distance": decision.get("distance"),
        "candidate_count": int(decision.get("candidate_count") or 0),
        "fallback_used": _bool_or_none(decision.get("fallback_used")),
        "time_stability_metric": compute_time_stability_metric(
            source,
            transformed,
            feature=feature,
            target=target,
            time_col=time_col,
        )
        if transformed is not None
        else None,
        "bundle_export_possible": bundle_export_possible,
        "error": error,
    }


def run_policy_comparison(
    df: pd.DataFrame | None = None,
    *,
    feature: str = "score",
    target: str = "target",
    time_col: str | None = "vintage",
) -> dict[str, Any]:
    """Compare standard, separate, forbid and merge policies on synthetic data."""

    df = make_policy_comparison_frame() if df is None else df.copy()
    rows: list[dict[str, Any]] = []
    details: dict[str, dict[str, Any]] = {}

    for config in POLICY_CONFIGS:
        name = config["name"]
        kwargs = dict(config["kwargs"])
        binner = RiskBands(max_bins=5, min_event_rate_diff=0.0, **kwargs)
        try:
            binner.fit(df, y=target, column=feature, time_col=time_col)
            transformed = binner.transform(df[[feature]])
            rows.append(
                summarize_policy_result(
                    policy_name=name,
                    binner=binner,
                    source=df,
                    transformed=transformed,
                    feature=feature,
                    target=target,
                    time_col=time_col,
                )
            )
            details[name] = {
                "binner": binner,
                "transformed_head": transformed.head(8),
                "missing_profile": binner.missing_profile_.copy(),
                "missing_decision_log": binner.missing_decision_log_.copy(),
                "missing_merge_candidates": getattr(
                    binner,
                    "missing_merge_candidates_",
                    pd.DataFrame(),
                ).copy(),
            }
        except ValueError as exc:
            rows.append(
                summarize_policy_result(
                    policy_name=name,
                    binner=None,
                    source=df,
                    transformed=None,
                    feature=feature,
                    target=target,
                    time_col=time_col,
                    error=str(exc),
                )
            )
            details[name] = {"error": str(exc)}

    comparison = pd.DataFrame(rows)
    return {"dataset": df, "comparison": comparison, "details": details}
