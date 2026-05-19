"""Synthetic credit-risk example for auditable missing merge policies."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from riskbands import RiskBands

FEATURES = ["bureau_score", "income", "internal_rating", "channel", "product"]
CATEGORICAL_FEATURES = ["internal_rating", "channel", "product"]


def make_credit_risk_missing_frame(n: int = 720) -> pd.DataFrame:
    """Create deterministic synthetic credit-risk data with informative missingness."""

    channels = ["branch", "digital", "partner"]
    products = ["card", "loan", "overdraft"]
    ratings = ["A", "B", "C", "D"]
    vintages = ["2024Q1", "2024Q2", "2024Q3", "2024Q4", "2025Q1", "2025Q2"]

    rows: list[dict[str, Any]] = []
    for idx in range(n):
        channel = channels[idx % len(channels)]
        product = products[(idx // 3) % len(products)]
        vintage = vintages[(idx // 17) % len(vintages)]
        rating = ratings[(idx // 11) % len(ratings)]

        score = 430 + (idx * 37) % 360
        income = 1800 + (idx * 911) % 13800
        risk = 0.04 + max(0.0, (680 - score) / 1500)
        risk += {"A": 0.00, "B": 0.035, "C": 0.075, "D": 0.135}[rating]
        risk += {"card": 0.015, "loan": 0.025, "overdraft": 0.055}[product]
        risk += {"branch": -0.005, "digital": 0.015, "partner": 0.035}[channel]
        risk += (vintages.index(vintage) - 2.5) * 0.005

        bureau_missing = (channel == "partner" and idx % 4 != 0) or (product == "overdraft" and idx % 9 == 0)
        income_missing = (channel == "digital" and idx % 5 == 0) or (income < 2800 and idx % 2 == 0)
        rating_missing = (channel == "partner" and product == "card") or (idx % 53 == 0)

        if bureau_missing:
            risk += 0.055
            score_value = np.nan
        else:
            score_value = float(score)
        if income_missing:
            risk += 0.035
            income_value = np.nan
        else:
            income_value = float(income)
            risk += max(0.0, (4500 - income) / 50000)
        if rating_missing:
            risk += 0.045
            rating_value = None
        else:
            rating_value = rating

        risk = min(max(risk, 0.015), 0.72)
        target = int(((idx * 73) % 1000) / 1000 < risk)
        rows.append(
            {
                "bureau_score": score_value,
                "income": income_value,
                "internal_rating": rating_value,
                "channel": channel,
                "product": product,
                "vintage": vintage,
                "target": target,
            }
        )

    return pd.DataFrame(rows)


def _fit_policy(df: pd.DataFrame, *, policy: str, criterion: str | None = None) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"missing_policy": policy}
    if criterion is not None:
        kwargs["missing_merge_criterion"] = criterion
        kwargs["missing_merge_fallback"] = "separate_bin"
    binner = RiskBands(
        max_bins=5,
        min_event_rate_diff=0.0,
        force_categorical=CATEGORICAL_FEATURES,
        **kwargs,
    ).fit(df, y="target", columns=FEATURES, time_col="vintage")
    transformed = binner.transform(df[FEATURES])
    transformed_woe = binner.transform(df[FEATURES], return_woe=True)
    return {
        "policy": policy,
        "criterion": criterion,
        "binner": binner,
        "transformed_head": transformed.head(8),
        "transformed_woe_head": transformed_woe.head(8),
        "missing_profile": binner.missing_profile_.copy(),
        "missing_decision_log": binner.missing_decision_log_.copy(),
        "missing_merge_candidates": getattr(binner, "missing_merge_candidates_", pd.DataFrame()).copy(),
    }


def _decision_for_variable(decisions: pd.DataFrame, variable: str) -> dict[str, Any]:
    rows = decisions.loc[decisions["variable"].astype(str) == variable]
    if rows.empty:
        return {}
    return rows.iloc[0].to_dict()


def _profile_for_variable(profile: pd.DataFrame, variable: str) -> dict[str, Any]:
    rows = profile.loc[profile["variable"].astype(str) == variable]
    if rows.empty:
        return {}
    return rows.iloc[0].to_dict()


def _comparison_rows(results: dict[str, dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for name, result in results.items():
        binner = result["binner"]
        decisions = result["missing_decision_log"]
        profile = result["missing_profile"]
        for variable in FEATURES:
            decision = _decision_for_variable(decisions, variable)
            missing_profile = _profile_for_variable(profile, variable)
            bin_rows = binner.bin_summary.loc[binner.bin_summary["variable"].astype(str) == variable]
            rows.append(
                {
                    "policy": name,
                    "merge_criterion": result["criterion"],
                    "variable": variable,
                    "n_bins": int(len(bin_rows)),
                    "iv": float(getattr(binner, "iv_by_variable_", pd.Series(dtype=float)).get(variable, np.nan)),
                    "missing_event_rate": missing_profile.get("event_rate_missing_fit"),
                    "missing_action": decision.get("action"),
                    "selected_bin": decision.get("selected_bin_label"),
                    "distance": decision.get("distance"),
                    "candidate_count": int(decision.get("candidate_count") or 0),
                    "fallback_used": bool(decision.get("fallback_used"))
                    if decision.get("fallback_used") is not None
                    else None,
                }
            )
    return pd.DataFrame(rows)


def _missing_rate_table(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for variable in FEATURES:
        missing_mask = df[variable].isna()
        rows.append(
            {
                "variable": variable,
                "missing_count": int(missing_mask.sum()),
                "missing_share": float(missing_mask.mean()),
                "target_rate_when_missing": float(df.loc[missing_mask, "target"].mean())
                if bool(missing_mask.any())
                else None,
                "target_rate_when_observed": float(df.loc[~missing_mask, "target"].mean())
                if bool((~missing_mask).any())
                else None,
            }
        )
    return pd.DataFrame(rows)


def _method_notes() -> list[str]:
    return [
        "Use separate_bin when missingness is itself a defensible segment to monitor.",
        "Use merge only after comparing it against separate_bin and reviewing the candidate distances.",
        "Prefer nearest_event_rate for direct event-rate explanations; "
        "prefer nearest_woe for scorecard-similarity review.",
        "Do not treat this synthetic example as regulatory validation or as evidence that merge is always better.",
    ]


def run_credit_risk_missing_merge_demo() -> dict[str, object]:
    """Run the credit-risk missing merge demo and return all audit tables."""

    df = make_credit_risk_missing_frame()
    results = {
        "separate_bin": _fit_policy(df, policy="separate_bin"),
        "merge_nearest_event_rate": _fit_policy(df, policy="merge", criterion="nearest_event_rate"),
        "merge_nearest_woe": _fit_policy(df, policy="merge", criterion="nearest_woe"),
    }
    return {
        "dataset": df,
        "missing_rates": _missing_rate_table(df),
        "policy_results": results,
        "comparison": _comparison_rows(results),
        "method_notes": _method_notes(),
    }


def _show(title: str, value: object) -> None:
    print(f"\n=== {title} ===")
    print(value)


def main() -> None:
    pd.set_option("display.max_columns", 50)
    pd.set_option("display.width", 180)

    results = run_credit_risk_missing_merge_demo()
    _show("Synthetic credit-risk data sample", results["dataset"].head(12))
    _show("Missing rates", results["missing_rates"])
    _show("Policy comparison", results["comparison"])

    for key in ["separate_bin", "merge_nearest_event_rate", "merge_nearest_woe"]:
        policy_result = results["policy_results"][key]
        _show(f"{key} missing_profile_", policy_result["missing_profile"])
        _show(f"{key} missing_decision_log_", policy_result["missing_decision_log"])
        _show(f"{key} missing_merge_candidates_", policy_result["missing_merge_candidates"])

    _show("Method notes", pd.Series(results["method_notes"], name="note"))


if __name__ == "__main__":
    main()
