import json

import numpy as np
import pandas as pd

from riskbands import Binner
from riskbands.reporting import save_binner_report


def _make_vintage_dataset(*, sparse_last_period: bool = False):
    rows = []
    periods = [202301, 202302, 202303]
    for period in periods:
        low_values = np.linspace(-3.0, -1.0, 10)
        mid_values = np.linspace(-0.4, 0.4, 10)
        high_values = np.linspace(1.0, 3.0, 10)

        if period == 202301:
            low_target = [0] * 10
            mid_target = [0] * 10
            high_target = [1] * 10
        elif period == 202302:
            low_target = [0] * 10
            mid_target = [1] * 10
            high_target = [1] * 10
        else:
            low_target = [1] * 10
            mid_target = [0] * 10
            high_target = [0] * 10

        for value, target in zip(low_values, low_target, strict=False):
            rows.append({"score": value, "month": period, "target": target})
        if not (sparse_last_period and period == 202303):
            for value, target in zip(mid_values, mid_target, strict=False):
                rows.append({"score": value, "month": period, "target": target})
            for value, target in zip(high_values, high_target, strict=False):
                rows.append({"score": value, "month": period, "target": target})

    df = pd.DataFrame(rows)
    X = df[["score", "month"]].reset_index(drop=True)
    y = df["target"].reset_index(drop=True)
    return X, y


def _fit_diagnostic_binner(X, y):
    binner = Binner(
        strategy="unsupervised",
        max_bins=3,
        min_event_rate_diff=0.0,
        monotonic="ascending",
        check_stability=True,
    )
    binner.fit(X, y, time_col="month")
    return binner


def test_temporal_bin_diagnostics_builds_full_grid_with_coverage_flags():
    X, y = _make_vintage_dataset(sparse_last_period=True)
    binner = _fit_diagnostic_binner(X, y)

    diagnostics = binner.temporal_bin_diagnostics(
        X,
        y,
        time_col="month",
        dataset_name="train",
        min_bin_count=8,
        min_time_coverage=1.0,
    )

    assert diagnostics["dataset"].eq("train").all()
    assert diagnostics["variable"].nunique() == 1
    assert diagnostics.shape[0] == 9
    assert {
        "variable",
        "bin",
        "month",
        "total_count",
        "event_count",
        "non_event_count",
        "bin_share",
        "event_rate",
        "woe",
        "iv_contribution",
        "coverage_flag",
        "alert_flags",
    } <= set(diagnostics.columns)
    assert (~diagnostics["coverage_flag"]).sum() >= 1
    assert diagnostics["missing_bin_flag"].any()


def test_temporal_variable_summary_flags_credit_relevant_instabilities():
    X, y = _make_vintage_dataset()
    binner = _fit_diagnostic_binner(X, y)

    diagnostics = binner.temporal_bin_diagnostics(
        X,
        y,
        time_col="month",
        dataset_name="oot",
        min_bin_count=12,
        min_time_coverage=1.0,
    )
    summary = binner.temporal_variable_summary(
        diagnostics=diagnostics,
        time_col="month",
        event_rate_std_threshold=0.10,
        woe_std_threshold=0.10,
        bin_share_std_threshold=0.01,
    )

    assert summary.shape[0] == 1
    row = summary.iloc[0]
    assert row["dataset"] == "oot"
    assert row["rare_bin_count"] > 0
    assert row["monotonic_break_period_count"] > 0
    assert row["ranking_reversal_period_count"] > 0
    assert "ranking_reversal" in row["alert_flags"]
    assert "monotonic_break" in row["alert_flags"]


def test_temporal_variable_summary_flags_low_coverage_bins():
    X, y = _make_vintage_dataset(sparse_last_period=True)
    binner = _fit_diagnostic_binner(X, y)

    diagnostics = binner.temporal_bin_diagnostics(
        X,
        y,
        time_col="month",
        dataset_name="validation",
        min_time_coverage=1.0,
    )
    summary = binner.temporal_variable_summary(diagnostics=diagnostics, time_col="month")

    row = summary.iloc[0]
    assert row["low_coverage_bin_count"] > 0
    assert "low_coverage" in row["alert_flags"]


def test_temporal_report_exports_diagnostics_layers(tmp_path):
    X, y = _make_vintage_dataset(sparse_last_period=True)
    binner = _fit_diagnostic_binner(X, y)
    diagnostics = binner.temporal_bin_diagnostics(X, y, time_col="month", dataset_name="train")
    summary = binner.temporal_variable_summary(diagnostics=diagnostics, time_col="month")

    report_path = tmp_path / "diag_report.json"
    save_binner_report(binner, report_path)
    payload = json.loads(report_path.read_text(encoding="utf-8"))

    assert "temporal_bin_diagnostics" in payload
    assert "temporal_variable_summary" in payload
    assert len(payload["temporal_variable_summary"]) == len(summary)


