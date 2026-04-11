import numpy as np
import pandas as pd

from riskbands import Binner
from riskbands.optuna_optimizer import (
    build_objective_components,
    optimize_bins,
    score_objective_components,
)


def _make_credit_vintage_dataset(*, unstable: bool = False):
    rows = []
    periods = [202301, 202302, 202303, 202304]
    for period in periods:
        low_values = np.linspace(-3.0, -1.0, 18)
        mid_values = np.linspace(-0.5, 0.5, 18)
        high_values = np.linspace(1.0, 3.0, 18)

        if unstable and period >= 202303:
            low_target = [1] * 18
            mid_target = [0] * 18
            high_target = [0] * 18
        else:
            low_target = [0] * 18
            mid_target = [0] * 18 if period == 202301 else [1] * 18
            high_target = [1] * 18

        for value, target in zip(low_values, low_target):
            rows.append({"score": value, "month": period, "target": target})
        for value, target in zip(mid_values, mid_target):
            rows.append({"score": value, "month": period, "target": target})
        for value, target in zip(high_values, high_target):
            rows.append({"score": value, "month": period, "target": target})

    df = pd.DataFrame(rows)
    X = df[["score", "month"]].reset_index(drop=True)
    y = df["target"].reset_index(drop=True)
    return X, y


def _fit_reference_binner(X, y):
    binner = Binner(
        strategy="unsupervised",
        max_bins=3,
        min_event_rate_diff=0.0,
        monotonic="ascending",
        check_stability=True,
    )
    binner.fit(X, y, time_col="month")
    return binner


def test_score_objective_components_penalizes_instability_and_rare_bins():
    stable_components = {
        "iv": 0.25,
        "separability": 0.30,
        "ks": 0.20,
        "temporal_score": 0.22,
        "coverage_ratio_min": 1.0,
        "rare_bin_count": 0,
        "event_rate_std_max": 0.02,
        "woe_std_max": 0.10,
        "bin_share_std_max": 0.01,
        "monotonic_break_period_count": 0,
        "ranking_reversal_period_count": 0,
    }
    unstable_components = {
        **stable_components,
        "temporal_score": 0.05,
        "coverage_ratio_min": 0.55,
        "rare_bin_count": 2,
        "event_rate_std_max": 0.25,
        "woe_std_max": 0.90,
        "bin_share_std_max": 0.12,
        "monotonic_break_period_count": 2,
        "ranking_reversal_period_count": 3,
    }

    stable_score = score_objective_components(stable_components)
    unstable_score = score_objective_components(unstable_components)

    assert stable_score["score"] > unstable_score["score"]
    assert stable_score["total_penalty"] < unstable_score["total_penalty"]
    assert unstable_score["penalties"]["ranking_reversal_penalty"] > 0
    assert unstable_score["penalties"]["rare_bin_penalty"] > 0


def test_build_objective_components_uses_temporal_diagnostics_signals():
    X, y = _make_credit_vintage_dataset(unstable=True)
    binner = _fit_reference_binner(X, y)

    components = build_objective_components(binner, X, y, time_col="month")

    assert components["iv"] >= 0
    assert components["temporal_score"] >= 0
    assert components["event_rate_std_max"] > 0
    assert components["woe_std_max"] > 0
    assert components["ranking_reversal_period_count"] > 0
    assert components["monotonic_break_period_count"] > 0


def test_optimize_bins_exposes_credit_objective_summary():
    X, y = _make_credit_vintage_dataset(unstable=False)

    best, binner = optimize_bins(
        X[["score"]],
        y,
        time_col="month",
        time_values=X["month"],
        n_trials=2,
        strategy="supervised",
    )

    assert 3 <= best["max_bins"] <= 10
    assert "score" in binner.objective_summary_
    assert "penalties" in binner.objective_summary_
    assert "components" in binner.objective_summary_
    assert np.isfinite(binner.objective_summary_["score"])


