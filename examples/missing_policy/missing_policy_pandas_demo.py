"""Small pandas demo for RiskBands missing policies."""

from __future__ import annotations

from tempfile import TemporaryDirectory

import numpy as np
import pandas as pd

from riskbands import RiskBands
from riskbands.reporting import load_bundle


FEATURES = ["score", "rating"]


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


def _show(title: str, value: object) -> None:
    print(f"\n=== {title} ===")
    print(value)


def run_pandas_missing_policy_demo() -> dict[str, object]:
    """Run standard, separate_bin and forbid examples without persistent files."""

    df = make_demo_frame()
    standard = _fit_policy(df, "standard")
    separate = _fit_policy(df, "separate_bin")

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

    _show("forbid fit error", results["forbid_fit_error"])
    _show("forbid transform error", results["forbid_transform_error"])
    _show("separate_bin bundle summary", results["bundle_summary"])


if __name__ == "__main__":
    main()
