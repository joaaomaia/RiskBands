"""Quickstart example demonstrating temporal stability with NASABinning.

For a more credit-oriented champion/challenger narrative, see
``examples/pd_vintage_champion_challenger/pd_vintage_champion_challenger.py``.
"""

from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nasabinning import NASABinner
from nasabinning.temporal_stability import ks_over_time, temporal_separability_score


def make_temporal_toy_data(seed: int = 0, n: int = 800) -> tuple[pd.DataFrame, pd.Series]:
    """Create a lightweight dataset with one score and multiple vintages."""
    rng = np.random.default_rng(seed)

    X = pd.DataFrame({"x": rng.normal(size=n)})
    X["month"] = rng.choice([202301, 202302, 202303, 202304], size=n)

    proba = 0.20 + 0.15 * X["x"] + 0.02 * (X["month"] - 202301)
    proba = np.clip(proba, 0.01, 0.99)
    y = pd.Series((rng.random(n) < proba).astype(int), name="target")
    return X, y


def run_temporal_stability_demo(seed: int = 0, n: int = 800) -> dict[str, object]:
    """Run the temporal quickstart and return the main artifacts."""
    X, y = make_temporal_toy_data(seed=seed, n=n)

    binner = NASABinner(
        strategy="supervised",
        check_stability=True,
        use_optuna=True,
        time_col="month",
        strategy_kwargs={
            "n_trials": 10,
            "objective_kwargs": {
                "minimums": {"iv": 0.05, "coverage_ratio": 0.75},
            },
        },
    )

    binner.fit(X, y, time_col="month")

    pivot = binner.stability_over_time(X, y, time_col="month")
    diagnostics = binner.temporal_bin_diagnostics(
        X,
        y,
        time_col="month",
        dataset_name="train",
    )
    summary = binner.temporal_variable_summary(diagnostics=diagnostics, time_col="month")
    audit_report = binner.variable_audit_report(
        X,
        y,
        time_col="month",
        dataset_name="train",
    )
    ks = ks_over_time(pivot)

    bins = binner.transform(X)["x"]
    separability = temporal_separability_score(
        pd.DataFrame({"x": X["x"], "bin": bins, "target": y, "time": X["month"]}),
        "x",
        "bin",
        "target",
        "time",
    )

    return {
        "X": X,
        "y": y,
        "binner": binner,
        "pivot": pivot,
        "diagnostics": diagnostics,
        "summary": summary,
        "audit_report": audit_report,
        "ks_over_time": ks,
        "temporal_separability": separability,
    }


def main() -> None:
    results = run_temporal_stability_demo()
    binner = results["binner"]

    print(f"Temporal separability: {results['temporal_separability']:.3f}")
    print(f"IV: {binner.iv_:.3f}")
    print(f"KS over time: {results['ks_over_time']:.3f}")
    print("Best params:", binner.best_params_)
    print("Objective summaries:", binner.objective_summaries_)
    print(results["diagnostics"].head())
    print(results["summary"][["variable", "temporal_score", "alert_flags"]])
    print(
        results["audit_report"][
            ["variable", "objective_score", "key_penalties", "rationale_summary"]
        ]
    )

    binner.plot_event_rate_stability(results["pivot"])
    binner.save_report("reports/temporal_stability_example.xlsx")


if __name__ == "__main__":
    main()
