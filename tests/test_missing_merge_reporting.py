import json

import pandas as pd

from riskbands import RiskBands
from tests.test_missing_merge_nearest_event_rate_pandas import fit_numeric_merge
from tests.test_missing_values_current_behavior import make_numeric_missing_frame


def test_report_exposes_missing_merge_summary_fields():
    binner, _ = fit_numeric_merge()

    report = binner.report()
    row = report.iloc[0]

    assert row["missing_policy"] == "merge"
    assert row["effective_missing_policy"] == "merge"
    assert row["missing_merge_criterion"] == "nearest_event_rate"
    assert row["missing_merge_fallback"] == "separate_bin"
    assert row["missing_merge_action"] == "missing_merged"
    assert row["missing_merge_status"] == "merged"
    assert row["missing_merged_into"] == binner.missing_decision_log_.iloc[0]["selected_bin_label"]
    assert row["missing_original_n"] == binner.missing_decision_log_.iloc[0]["n_missing_fit"]


def test_save_report_json_contains_missing_merge_fields(tmp_path):
    binner, _ = fit_numeric_merge()
    path = tmp_path / "report.json"

    binner.save_report(path)
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["missing_policy"] == "merge"
    assert payload["effective_missing_policy"] == "merge"
    assert payload["missing_merge_criterion"] == "nearest_event_rate"
    assert payload["missing_merge_fallback"] == "separate_bin"
    assert payload["missing_profile"][0]["bin_label"] == "Missing"
    assert payload["missing_decision_log"][0]["action"] == "missing_merged"
    assert payload["missing_merge_candidates"][0]["selected"] is True
    assert payload["missing_merge_map"]


def test_missing_merge_reporting_does_not_revert_standard_objective_name():
    binner, _ = fit_numeric_merge()

    report = binner.report()

    assert "legacy" not in set(report["score_strategy"].astype(str))
    assert "legacy" not in set(report["objective_source"].astype(str))
    assert report.iloc[0]["objective_source"] == "derived_standard_objective"


def test_standard_separate_bin_and_forbid_reporting_do_not_regress():
    standard = RiskBands(missing_policy="standard", min_event_rate_diff=0.0).fit(
        make_numeric_missing_frame(),
        y="target",
        column="score",
    )
    separate = RiskBands(missing_policy="separate_bin", min_event_rate_diff=0.0).fit(
        make_numeric_missing_frame(),
        y="target",
        column="score",
    )
    forbid = RiskBands(missing_policy="forbid", min_event_rate_diff=0.0).fit(
        pd.DataFrame({"score": [-5.0, -1.0, 1.0, 5.0], "target": [0, 0, 1, 1]}),
        y="target",
        column="score",
    )

    assert standard.report().iloc[0]["missing_policy"] == "standard"
    assert separate.report().iloc[0]["missing_policy"] == "separate_bin"
    assert forbid.report().iloc[0]["missing_policy"] == "forbid"
    assert standard.save_report is not None
