"""Compare RiskBands missing policies on a deterministic synthetic dataset."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _comparison_utils import run_policy_comparison  # noqa: E402


def _show(title: str, value: object) -> None:
    print(f"\n=== {title} ===")
    print(value)


def run_missing_policy_comparison_demo() -> dict[str, object]:
    """Run a side-by-side diagnostic for standard, separate, merge and forbid."""

    results = run_policy_comparison()
    comparison = results["comparison"].copy()
    ordered_columns = [
        "policy",
        "merge_criterion",
        "n_bins",
        "iv",
        "missing_event_rate",
        "missing_action",
        "selected_bin",
        "distance",
        "candidate_count",
        "fallback_used",
        "time_stability_metric",
        "bundle_export_possible",
        "error",
    ]
    results["comparison"] = comparison.loc[:, ordered_columns]
    return results


def main() -> None:
    pd.set_option("display.max_columns", 40)
    pd.set_option("display.width", 160)

    results = run_missing_policy_comparison_demo()
    _show("Synthetic data sample", results["dataset"].head(10))
    _show("Policy comparison", results["comparison"])

    for key in ["merge_nearest_event_rate", "merge_nearest_woe"]:
        detail = results["details"][key]
        _show(f"{key} missing_decision_log_", detail["missing_decision_log"])
        _show(f"{key} missing_merge_candidates_", detail["missing_merge_candidates"])

    _show("forbid expected error", results["details"]["forbid"]["error"])


if __name__ == "__main__":
    main()
