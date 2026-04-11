import json

import numpy as np
import pandas as pd

from riskbands import Binner
from riskbands.compare import BinComparator
from riskbands.reporting import (
    build_candidate_profile_report,
    build_candidate_winner_report,
    save_binner_report,
)


def _make_vintage_dataset(*, sparse_last_period: bool = False):
    rows = []
    periods = [202301, 202302, 202303]
    for period in periods:
        low_values = np.linspace(-3.0, -1.0, 12)
        mid_values = np.linspace(-0.4, 0.4, 12)
        high_values = np.linspace(1.0, 3.0, 12)

        if period == 202301:
            low_target = [0] * 12
            mid_target = [0] * 12
            high_target = [1] * 12
        elif period == 202302:
            low_target = [0] * 12
            mid_target = [1] * 12
            high_target = [1] * 12
        else:
            low_target = [1] * 12
            mid_target = [0] * 12
            high_target = [0] * 12

        for value, target in zip(low_values, low_target):
            rows.append({"score": value, "month": period, "target": target})
        if not (sparse_last_period and period == 202303):
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


def test_variable_audit_report_consolidates_temporal_and_objective_signals():
    X, y = _make_vintage_dataset(sparse_last_period=True)
    binner = _fit_reference_binner(X, y)

    report = binner.variable_audit_report(
        X,
        y,
        time_col="month",
        dataset_name="train",
        candidate_name="selected",
    )

    assert report.shape[0] == 1
    assert {
        "variable",
        "candidate_name",
        "selected_strategy",
        "cut_summary",
        "objective_score",
        "key_penalties",
        "selection_basis",
        "rationale_summary",
        "coverage_ratio_min",
        "temporal_score",
    } <= set(report.columns)
    row = report.iloc[0]
    assert row["candidate_name"] == "selected"
    assert row["selected_strategy"] == "unsupervised"
    assert isinstance(row["rationale_summary"], str) and row["rationale_summary"]


def test_candidate_profile_and_winner_reports_identify_profile_winners():
    candidate_reports = pd.DataFrame(
        [
            {
                "dataset": "comparison",
                "variable": "score",
                "candidate_name": "static_star",
                "selected_strategy": "supervised",
                "iv": 0.35,
                "ks": 0.24,
                "temporal_score": 0.05,
                "coverage_ratio_min": 0.65,
                "rare_bin_count": 2,
                "ranking_reversal_period_count": 2,
                "objective_score": 0.12,
                "objective_total_penalty": 0.18,
                "separability_component": 0.02,
                "iv_component": 0.20,
                "ks_component": 0.11,
                "temporal_score_component": 0.03,
                "rare_bin_penalty": 0.06,
                "coverage_gap_penalty": 0.03,
                "event_rate_volatility_penalty": 0.04,
                "woe_volatility_penalty": 0.01,
                "share_volatility_penalty": 0.01,
                "monotonic_break_penalty": 0.01,
                "ranking_reversal_penalty": 0.02,
                "iv_shortfall_penalty": 0.00,
                "temporal_shortfall_penalty": 0.01,
                "key_drivers": "iv_component=0.200; ks_component=0.110",
                "key_penalties": "rare_bin_penalty=0.060; event_rate_volatility_penalty=0.040",
                "selection_basis": "discrimination-led",
                "alert_flags": "rare_bins;ranking_reversal",
                "rationale_summary": "Resumo estatico.",
            },
            {
                "dataset": "comparison",
                "variable": "score",
                "candidate_name": "stable_star",
                "selected_strategy": "unsupervised",
                "iv": 0.18,
                "ks": 0.10,
                "temporal_score": 0.33,
                "coverage_ratio_min": 0.95,
                "rare_bin_count": 1,
                "ranking_reversal_period_count": 0,
                "objective_score": 0.18,
                "objective_total_penalty": 0.03,
                "separability_component": 0.15,
                "iv_component": 0.09,
                "ks_component": 0.04,
                "temporal_score_component": 0.20,
                "rare_bin_penalty": 0.02,
                "coverage_gap_penalty": 0.00,
                "event_rate_volatility_penalty": 0.01,
                "woe_volatility_penalty": 0.00,
                "share_volatility_penalty": 0.00,
                "monotonic_break_penalty": 0.00,
                "ranking_reversal_penalty": 0.00,
                "iv_shortfall_penalty": 0.00,
                "temporal_shortfall_penalty": 0.00,
                "key_drivers": "temporal_score_component=0.200; separability_component=0.150",
                "key_penalties": "rare_bin_penalty=0.020",
                "selection_basis": "stability-led",
                "alert_flags": "rare_bins",
                "rationale_summary": "Resumo estavel.",
            },
            {
                "dataset": "comparison",
                "variable": "score",
                "candidate_name": "balanced_star",
                "selected_strategy": "supervised",
                "iv": 0.26,
                "ks": 0.16,
                "temporal_score": 0.24,
                "coverage_ratio_min": 0.90,
                "rare_bin_count": 0,
                "ranking_reversal_period_count": 0,
                "objective_score": 0.19,
                "objective_total_penalty": 0.05,
                "separability_component": 0.10,
                "iv_component": 0.13,
                "ks_component": 0.07,
                "temporal_score_component": 0.16,
                "rare_bin_penalty": 0.00,
                "coverage_gap_penalty": 0.00,
                "event_rate_volatility_penalty": 0.01,
                "woe_volatility_penalty": 0.01,
                "share_volatility_penalty": 0.01,
                "monotonic_break_penalty": 0.00,
                "ranking_reversal_penalty": 0.00,
                "iv_shortfall_penalty": 0.00,
                "temporal_shortfall_penalty": 0.00,
                "key_drivers": "temporal_score_component=0.160; iv_component=0.130",
                "key_penalties": "event_rate_volatility_penalty=0.010",
                "selection_basis": "balanced",
                "alert_flags": "",
                "rationale_summary": "Resumo equilibrado.",
            },
        ]
    )

    profiles = build_candidate_profile_report(candidate_reports)
    winners = build_candidate_winner_report(profiles)

    assert winners.shape[0] == 1
    row = winners.iloc[0]
    assert row["best_static_candidate"] == "static_star"
    assert row["best_temporal_candidate"] == "stable_star"
    assert row["best_balanced_candidate"] == "balanced_star"
    assert row["selected_candidate"] == "balanced_star"
    assert isinstance(row["winner_rationale"], str) and row["winner_rationale"]


def test_bin_comparator_exposes_audit_profiles_and_winner_summary():
    X, y = _make_vintage_dataset(sparse_last_period=True)
    comparator = BinComparator(
        [
            {"strategy": "supervised", "max_bins": 4, "name": "sup"},
            {"strategy": "unsupervised", "method": "quantile", "n_bins": 3, "name": "unsup"},
        ],
        time_col="month",
    )

    summary = comparator.fit_compare(X, y)
    audit = comparator.candidate_audit_report()
    profiles = comparator.candidate_profile_summary()
    winners = comparator.winner_summary()

    assert {"sup", "unsup"} <= set(summary.index)
    assert {"candidate_name", "objective_score", "rationale_summary"} <= set(audit.columns)
    assert {"static_profile_score", "temporal_profile_score", "balanced_profile_score"} <= set(
        profiles.columns
    )
    assert {"selected_candidate", "winner_rationale"} <= set(winners.columns)
    assert winners["selected_candidate"].notna().all()


def test_save_report_exports_variable_audit_layer(tmp_path):
    X, y = _make_vintage_dataset(sparse_last_period=True)
    binner = _fit_reference_binner(X, y)
    binner.temporal_bin_diagnostics(X, y, time_col="month", dataset_name="train")
    binner.temporal_variable_summary(time_col="month", diagnostics=binner._temporal_bin_diagnostics_)
    binner.variable_audit_report(X, y, time_col="month", dataset_name="train")

    report_path = tmp_path / "variable_audit_report.json"
    save_binner_report(binner, report_path)
    payload = json.loads(report_path.read_text(encoding="utf-8"))

    assert "variable_audit_report" in payload
    assert len(payload["variable_audit_report"]) == 1


