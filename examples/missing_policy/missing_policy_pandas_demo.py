"""Small pandas demo for RiskBands missing policies."""

from __future__ import annotations

from tempfile import TemporaryDirectory

import numpy as np
import pandas as pd

from riskbands import RiskBands
from riskbands.reporting import load_bundle


FEATURES = ["score", "rating"]
MERGE_FEATURE = "score"


def make_demo_frame() -> pd.DataFrame:
    """Create a tiny synthetic credit-risk-like dataset with missing values."""

    score_pattern = [
        410.0,
        450.0,
        480.0,
        np.nan,
        520.0,
        560.0,
        590.0,
        630.0,
        np.nan,
        680.0,
        710.0,
        750.0,
    ]
    rating_pattern = [
        "A",
        "A",
        "B",
        "B",
        None,
        "C",
        "C",
        "D",
        "D",
        None,
        "E",
        "E",
    ]
    target_pattern = [0, 0, 0, 1, 0, 1, 0, 1, 1, 1, 1, 0]

    return pd.DataFrame(
        {
            "score": score_pattern * 4,
            "rating": rating_pattern * 4,
            "target": target_pattern * 4,
        }
    )


def make_missing_merge_frame() -> pd.DataFrame:
    """Create a synthetic single-feature dataset for missing merge demos."""

    score: list[float] = []
    target: list[int] = []
    for value, event_rate in [(-5.0, 0.05), (-3.0, 0.20), (0.0, 0.50), (3.0, 0.80), (5.0, 0.95)]:
        n = 40
        events = int(n * event_rate)
        score.extend([value] * n)
        target.extend([1] * events + [0] * (n - events))

    score.extend([np.nan] * 40)
    target.extend([1] * 20 + [0] * 20)

    return pd.DataFrame({"score": score, "target": target})


def _fit_policy(df: pd.DataFrame, policy: str) -> dict[str, object]:
    binner = RiskBands(
        max_bins=4,
        min_event_rate_diff=0.0,
        force_categorical=["rating"],
        missing_policy=policy,
    )
    binner.fit(df, y="target", columns=FEATURES, validate=True)
    transformed = binner.transform(df[FEATURES], validate=True)

    return {
        "policy": policy,
        "transformed_head": transformed.head(8),
        "missing_profile": binner.missing_profile_.copy(),
        "missing_decision_log": binner.missing_decision_log_.copy(),
        "binner": binner,
    }


def _fit_merge_policy(df: pd.DataFrame, criterion: str) -> dict[str, object]:
    binner = RiskBands(
        max_bins=5,
        min_event_rate_diff=0.0,
        missing_policy="merge",
        missing_merge_criterion=criterion,
        missing_merge_fallback="separate_bin",
    )
    binner.fit(df, y="target", column=MERGE_FEATURE, validate=True)
    transformed = binner.transform(pd.DataFrame({MERGE_FEATURE: [np.nan, -5.0, 0.0, 5.0]}), validate=True)
    transformed_woe = binner.transform(
        pd.DataFrame({MERGE_FEATURE: [np.nan, -5.0, 0.0, 5.0]}),
        return_woe=True,
    )

    with TemporaryDirectory(prefix=f"riskbands_missing_merge_{criterion}_") as tmpdir:
        binner.export_bundle(tmpdir)
        bundle = load_bundle(tmpdir)
        bundle_summary = {
            "missing_policy": bundle["missing_policy"],
            "effective_missing_policy": bundle["effective_missing_policy"],
            "missing_merge_criterion": bundle["missing_merge_criterion"],
            "missing_merge_fallback": bundle["missing_merge_fallback"],
            "missing_merge_candidates_rows": len(bundle["missing_merge_candidates"]),
            "missing_merge_map": bundle["missing_merge_map"],
        }

    return {
        "criterion": criterion,
        "transformed": transformed,
        "transformed_woe": transformed_woe,
        "missing_profile": binner.missing_profile_.copy(),
        "missing_decision_log": binner.missing_decision_log_.copy(),
        "missing_merge_candidates": binner.missing_merge_candidates_.copy(),
        "missing_merge_map": dict(binner.missing_merge_map_),
        "bundle_summary": bundle_summary,
        "binner": binner,
    }


def _show(title: str, value: object) -> None:
    print(f"\n=== {title} ===")
    print(value)


def run_pandas_missing_policy_demo() -> dict[str, object]:
    """Run standard, separate_bin, forbid and merge examples without persistent files."""

    df = make_demo_frame()
    merge_df = make_missing_merge_frame()
    standard = _fit_policy(df, "standard")
    separate = _fit_policy(df, "separate_bin")
    merge_nearest_event_rate = _fit_merge_policy(merge_df, "nearest_event_rate")
    merge_nearest_woe = _fit_merge_policy(merge_df, "nearest_woe")

    try:
        RiskBands(
            max_bins=4,
            min_event_rate_diff=0.0,
            force_categorical=["rating"],
            missing_policy="forbid",
        ).fit(df, y="target", columns=FEATURES)
    except ValueError as exc:
        forbid_fit_error = str(exc)
    else:  # pragma: no cover - this would mean the policy contract changed.
        forbid_fit_error = "UNEXPECTED: forbid did not fail on missing fit data."

    clean_df = df.dropna(subset=FEATURES).copy()
    forbid_clean = RiskBands(
        max_bins=4,
        min_event_rate_diff=0.0,
        force_categorical=["rating"],
        missing_policy="forbid",
    ).fit(clean_df, y="target", columns=FEATURES)
    try:
        forbid_clean.transform(df[FEATURES])
    except ValueError as exc:
        forbid_transform_error = str(exc)
    else:  # pragma: no cover - this would mean the policy contract changed.
        forbid_transform_error = "UNEXPECTED: forbid did not fail on missing transform data."

    with TemporaryDirectory(prefix="riskbands_missing_policy_") as tmpdir:
        separate["binner"].export_bundle(tmpdir)
        bundle = load_bundle(tmpdir)
        bundle_summary = {
            "missing_policy": bundle["missing_policy"],
            "effective_missing_policy": bundle["effective_missing_policy"],
            "missing_profile_rows": len(bundle["missing_profile"]),
            "missing_decision_log_rows": len(bundle["missing_decision_log"]),
        }

    return {
        "dataset": df,
        "standard": standard,
        "separate_bin": separate,
        "merge_dataset": merge_df,
        "merge_nearest_event_rate": merge_nearest_event_rate,
        "merge_nearest_woe": merge_nearest_woe,
        "forbid_fit_error": forbid_fit_error,
        "forbid_transform_error": forbid_transform_error,
        "bundle_summary": bundle_summary,
    }


def main() -> None:
    results = run_pandas_missing_policy_demo()

    _show("Synthetic input", results["dataset"].head(10))

    for policy in ["standard", "separate_bin"]:
        result = results[policy]
        _show(f"{policy} transformed head", result["transformed_head"])
        _show(f"{policy} missing_profile_", result["missing_profile"])
        _show(f"{policy} missing_decision_log_", result["missing_decision_log"])

    _show("Merge synthetic input", results["merge_dataset"].head(10))
    for key in ["merge_nearest_event_rate", "merge_nearest_woe"]:
        result = results[key]
        _show(f"{key} transformed", result["transformed"])
        _show(f"{key} transformed return_woe", result["transformed_woe"])
        _show(f"{key} missing_profile_", result["missing_profile"])
        _show(f"{key} missing_decision_log_", result["missing_decision_log"])
        _show(f"{key} missing_merge_candidates_", result["missing_merge_candidates"])
        _show(f"{key} missing_merge_map_", result["missing_merge_map"])
        _show(f"{key} bundle summary", result["bundle_summary"])

    _show("forbid fit error", results["forbid_fit_error"])
    _show("forbid transform error", results["forbid_transform_error"])
    _show("separate_bin bundle summary", results["bundle_summary"])


if __name__ == "__main__":
    main()
