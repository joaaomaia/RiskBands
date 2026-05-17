import json

from riskbands import RiskBands
from tests.test_missing_values_current_behavior import make_categorical_missing_frame, make_numeric_missing_frame


def test_missing_policy_reporting_exposes_missing_profile_and_decisions(tmp_path):
    df = make_categorical_missing_frame()
    binner = RiskBands(
        force_categorical=["grade"],
        missing_policy="separate_bin",
        min_event_rate_diff=0.0,
    ).fit(df, y="target", column="grade", validate=True)

    bundle_dir = tmp_path / "bundle"
    binner.export_bundle(bundle_dir)

    assert not binner.missing_profile_.empty
    assert not binner.missing_decision_log_.empty
    assert (bundle_dir / "missing_profile.csv").exists()
    assert (bundle_dir / "missing_decision_log.csv").exists()
    assert binner.fit_validation_report_["summary"]["variables_with_missing_bins"] == 1


def test_save_report_json_contains_missing_policy_fields(tmp_path):
    df = make_numeric_missing_frame()
    binner = RiskBands(missing_policy="separate_bin", min_event_rate_diff=0.0).fit(
        df,
        y="target",
        column="score",
    )
    path = tmp_path / "report.json"

    binner.save_report(path)
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["missing_policy"] == "separate_bin"
    assert payload["effective_missing_policy"] == "separate_bin"
    assert payload["missing_profile"][0]["bin_label"] == "Missing"


def test_standard_reporting_preserves_missing_out_of_bin_summary():
    df = make_numeric_missing_frame()
    binner = RiskBands(missing_policy="standard", min_event_rate_diff=0.0).fit(
        df,
        y="target",
        column="score",
    )

    assert "Missing" not in set(binner.bin_summary["bin"].astype(str))
    assert "Missing" in set(binner.fit_profile_["bin_label"].astype(str))
