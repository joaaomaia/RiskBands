import numpy as np
import pandas as pd

from riskbands import Binner
from riskbands.objectives import build_objective_components, score_objective_components
from riskbands.optuna_optimizer import optimize_bins


def _make_vintage_dataset(mode: str = "stable") -> tuple[pd.DataFrame, pd.Series]:
    rows = []
    periods = [202301, 202302, 202303, 202304]

    for period in periods:
        low_values = np.linspace(-3.0, -1.0, 18)
        mid_values = np.linspace(-0.4, 0.4, 18)
        high_values = np.linspace(1.0, 3.0, 18)

        if mode == "stable":
            low_target = [0] * 18
            mid_target = [0] * 9 + [1] * 9
            high_target = [1] * 18
        elif mode == "inversion":
            if period <= 202302:
                low_target = [0] * 18
                mid_target = [0] * 9 + [1] * 9
                high_target = [1] * 18
            else:
                low_target = [1] * 18
                mid_target = [0] * 9 + [1] * 9
                high_target = [0] * 18
        elif mode == "sparse_noisy":
            low_target = [0] * 18
            mid_target = [0] * 18 if period % 2 else [1] * 18
            high_target = [1] * 18
            if period == 202304:
                mid_values = np.linspace(-0.1, 0.1, 4)
                mid_target = [1, 0, 1, 0]
                high_values = np.linspace(1.0, 2.0, 5)
                high_target = [1, 1, 0, 1, 0]
        elif mode == "short_imbalanced":
            if period > 202302:
                continue
            low_values = np.linspace(-3.0, -1.5, 24 if period == 202301 else 30)
            mid_values = np.linspace(-0.1, 0.1, 3)
            high_values = np.linspace(1.0, 2.0, 2 if period == 202301 else 3)
            low_target = [0] * len(low_values)
            mid_target = [0, 1, 0]
            high_target = [1] * len(high_values)
        else:
            raise ValueError(f"Unsupported mode: {mode}")

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


def _fit_reference_binner(X: pd.DataFrame, y: pd.Series, *, score_strategy: str = "generalization_v1") -> Binner:
    binner = Binner(
        strategy="unsupervised",
        max_bins=3,
        min_event_rate_diff=0.0,
        monotonic="ascending",
        check_stability=True,
        score_strategy=score_strategy,
    )
    binner.fit(X, y, time_col="month")
    return binner


def test_legacy_strategy_remains_default_and_maximization_oriented():
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
        "event_rate_std_max": 0.30,
        "woe_std_max": 0.90,
        "bin_share_std_max": 0.12,
        "monotonic_break_period_count": 2,
        "ranking_reversal_period_count": 3,
    }

    stable_score = score_objective_components(stable_components)
    unstable_score = score_objective_components(unstable_components)

    assert stable_score["score_strategy"] == "legacy"
    assert stable_score["objective_direction"] == "maximize"
    assert stable_score["score"] > unstable_score["score"]


def test_generalization_v1_runs_without_optuna_and_emits_detailed_audit_columns():
    X, y = _make_vintage_dataset(mode="inversion")
    binner = _fit_reference_binner(X, y)

    report = binner.variable_audit_report(
        X,
        y,
        time_col="month",
        dataset_name="train",
    )

    row = report.iloc[0]
    assert row["score_strategy"] == "generalization_v1"
    assert row["objective_direction"] == "minimize"
    assert np.isfinite(row["objective_score"])
    assert np.isfinite(row["objective_preference_score"])
    assert {
        "objective_raw_temporal_variance",
        "objective_raw_window_drift",
        "objective_raw_rank_inversion",
        "objective_norm_temporal_variance",
        "objective_norm_separation_penalty",
        "objective_weight_temporal_variance_weight",
        "objective_weight_separation_weight",
        "woe_shrinkage_strength",
    } <= set(report.columns)


def test_generalization_v1_integrates_with_optuna():
    X, y = _make_vintage_dataset(mode="stable")

    best, binner = optimize_bins(
        X[["score"]],
        y,
        time_col="month",
        time_values=X["month"],
        n_trials=2,
        objective_kwargs={"score_strategy": "generalization_v1"},
        strategy="supervised",
    )

    assert 3 <= best["max_bins"] <= 10
    assert binner.objective_summary_["score_strategy"] == "generalization_v1"
    assert binner.objective_summary_["objective_direction"] == "minimize"
    assert np.isfinite(binner.objective_summary_["score"])


def test_generalization_weights_change_final_score():
    components = {
        "temporal_variance": 0.03,
        "window_drift": 0.04,
        "rank_inversion": 0.10,
        "separation": 0.08,
        "entropy": 0.12,
        "psi": 0.06,
    }

    default_score = score_objective_components(
        components,
        objective_kwargs={"score_strategy": "generalization_v1"},
    )
    weighted_score = score_objective_components(
        components,
        objective_kwargs={
            "score_strategy": "generalization_v1",
            "weights": {
                "separation_weight": 0.40,
                "temporal_variance_weight": 0.15,
                "window_drift_weight": 0.10,
                "rank_inversion_weight": 0.15,
                "entropy_weight": 0.05,
                "psi_weight": 0.15,
            },
        },
    )

    assert default_score["score"] != weighted_score["score"]


def test_generalization_normalization_is_finite_on_degenerate_inputs():
    details = score_objective_components(
        {
            "temporal_variance": 0.0,
            "window_drift": 0.0,
            "rank_inversion": 0.0,
            "separation": 0.0,
            "entropy": 0.0,
            "psi": 0.0,
        },
        objective_kwargs={"score_strategy": "generalization_v1"},
    )

    assert np.isfinite(details["score"])
    assert all(0.0 <= value <= 1.0 for value in details["normalized_components"].values())


def test_woe_shrinkage_reduces_noisy_temporal_components():
    X, y = _make_vintage_dataset(mode="sparse_noisy")
    binner = _fit_reference_binner(X, y)

    no_shrink = build_objective_components(
        binner,
        X,
        y,
        time_col="month",
        objective_kwargs={
            "score_strategy": "generalization_v1",
            "woe_shrinkage_strength": 0.0,
        },
    )
    strong_shrink = build_objective_components(
        binner,
        X,
        y,
        time_col="month",
        objective_kwargs={
            "score_strategy": "generalization_v1",
            "woe_shrinkage_strength": 120.0,
        },
    )

    assert strong_shrink["temporal_variance"] <= no_shrink["temporal_variance"]
    assert strong_shrink["window_drift"] <= no_shrink["window_drift"]


def test_separation_prevents_stable_but_useless_candidate_from_winning():
    stable_but_useless = score_objective_components(
        {
            "temporal_variance": 0.002,
            "window_drift": 0.003,
            "rank_inversion": 0.0,
            "separation": 0.005,
            "entropy": 0.03,
            "psi": 0.005,
        },
        objective_kwargs={"score_strategy": "generalization_v1"},
    )
    useful_but_slightly_noisier = score_objective_components(
        {
            "temporal_variance": 0.015,
            "window_drift": 0.020,
            "rank_inversion": 0.03,
            "separation": 0.18,
            "entropy": 0.05,
            "psi": 0.03,
        },
        objective_kwargs={"score_strategy": "generalization_v1"},
    )

    assert useful_but_slightly_noisier["score"] < stable_but_useless["score"]


def test_short_series_and_imbalanced_bins_remain_robust():
    X, y = _make_vintage_dataset(mode="short_imbalanced")
    binner = _fit_reference_binner(X, y)

    report = binner.variable_audit_report(X, y, time_col="month", dataset_name="short")

    row = report.iloc[0]
    assert np.isfinite(row["objective_score"])
    assert np.isfinite(row["objective_raw_entropy"])
    assert np.isfinite(row["objective_raw_psi"])


def test_rank_inversion_penalty_reacts_to_real_inversions():
    stable_X, stable_y = _make_vintage_dataset(mode="stable")
    inversion_X, inversion_y = _make_vintage_dataset(mode="inversion")

    stable_binner = _fit_reference_binner(stable_X, stable_y)
    inversion_binner = _fit_reference_binner(inversion_X, inversion_y)

    stable_components = build_objective_components(
        stable_binner,
        stable_X,
        stable_y,
        time_col="month",
        objective_kwargs={"score_strategy": "generalization_v1"},
    )
    inversion_components = build_objective_components(
        inversion_binner,
        inversion_X,
        inversion_y,
        time_col="month",
        objective_kwargs={"score_strategy": "generalization_v1"},
    )

    assert inversion_components["rank_inversion"] > stable_components["rank_inversion"]
