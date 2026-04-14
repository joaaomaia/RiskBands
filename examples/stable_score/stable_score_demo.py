"""Minimal demo contrasting legacy scoring with the stable strategy."""

from __future__ import annotations

import numpy as np
import pandas as pd

from riskbands import BinComparator


def _make_demo_dataset(seed: int = 21) -> tuple[pd.DataFrame, pd.Series]:
    rng = np.random.default_rng(seed)
    rows = []
    periods = [202301, 202302, 202303, 202304, 202305]

    for period in periods:
        low = rng.normal(loc=-2.2, scale=0.25, size=45)
        mid = rng.normal(loc=0.0, scale=0.20, size=40)
        high = rng.normal(loc=2.1, scale=0.30, size=45)

        if period <= 202303:
            low_target = [0] * 45
            mid_target = [0] * 20 + [1] * 20
            high_target = [1] * 45
        else:
            low_target = [1] * 45
            mid_target = [0] * 25 + [1] * 15
            high_target = [0] * 45

        for value, target in zip(low, low_target):
            rows.append({"score": float(value), "month": period, "target": int(target)})
        for value, target in zip(mid, mid_target):
            rows.append({"score": float(value), "month": period, "target": int(target)})
        for value, target in zip(high, high_target):
            rows.append({"score": float(value), "month": period, "target": int(target)})

    df = pd.DataFrame(rows)
    X = df[["score", "month"]].reset_index(drop=True)
    y = df["target"].reset_index(drop=True)
    return X, y


def _candidate_configs(score_strategy: str) -> list[dict]:
    shared = {
        "check_stability": True,
        "score_strategy": score_strategy,
    }
    if score_strategy == "stable":
        shared.update(
            normalization_strategy="absolute",
            woe_shrinkage_strength=40.0,
        )

    return [
        {
            "name": "static_aggressive",
            "strategy": "supervised",
            "max_bins": 6,
            "min_event_rate_diff": 0.0,
            "monotonic": "ascending",
            **shared,
        },
        {
            "name": "compact_monotonic",
            "strategy": "supervised",
            "max_bins": 4,
            "min_event_rate_diff": 0.03,
            "monotonic": "ascending",
            **shared,
        },
        {
            "name": "temporal_quantile_3",
            "strategy": "unsupervised",
            "method": "quantile",
            "n_bins": 3,
            "min_event_rate_diff": 0.0,
            "monotonic": "ascending",
            **shared,
        },
    ]


def _run_single_comparison(X: pd.DataFrame, y: pd.Series, *, score_strategy: str) -> dict[str, pd.DataFrame]:
    comparator = BinComparator(_candidate_configs(score_strategy), time_col="month")
    fit_summary = comparator.fit_compare(X, y)
    candidate_audit = comparator.candidate_audit_report()
    winner_summary = comparator.winner_summary()
    return {
        "fit_summary": fit_summary,
        "candidate_audit": candidate_audit,
        "winner_summary": winner_summary,
    }


def run_stable_score_demo(seed: int = 21) -> dict[str, object]:
    X, y = _make_demo_dataset(seed=seed)
    legacy = _run_single_comparison(X, y, score_strategy="legacy")
    stable = _run_single_comparison(X, y, score_strategy="stable")

    comparison = pd.DataFrame(
        [
            {
                "score_strategy": "legacy",
                "selected_candidate": legacy["winner_summary"].iloc[0]["selected_candidate"],
                "best_temporal_candidate": legacy["winner_summary"].iloc[0]["best_temporal_candidate"],
                "best_balanced_candidate": legacy["winner_summary"].iloc[0]["best_balanced_candidate"],
            },
            {
                "score_strategy": "stable",
                "selected_candidate": stable["winner_summary"].iloc[0]["selected_candidate"],
                "best_temporal_candidate": stable["winner_summary"].iloc[0]["best_temporal_candidate"],
                "best_balanced_candidate": stable["winner_summary"].iloc[0]["best_balanced_candidate"],
            },
        ]
    )

    return {
        "dataset": pd.concat([X, y.rename("target")], axis=1),
        "legacy_fit_summary": legacy["fit_summary"],
        "legacy_candidate_audit": legacy["candidate_audit"],
        "legacy_winner_summary": legacy["winner_summary"],
        "stable_fit_summary": stable["fit_summary"],
        "stable_candidate_audit": stable["candidate_audit"],
        "stable_winner_summary": stable["winner_summary"],
        "selection_comparison": comparison,
        "baseline_note": (
            "For a pure OptimalBinning baseline, use the existing "
            "examples/pd_vintage_benchmark/ benchmark suite."
        ),
    }


if __name__ == "__main__":
    results = run_stable_score_demo()
    print("Selection comparison:")
    print(results["selection_comparison"])
    print("\nLegacy winner:")
    print(results["legacy_winner_summary"])
    print("\nStable winner:")
    print(results["stable_winner_summary"])
    print("\nBaseline note:")
    print(results["baseline_note"])
