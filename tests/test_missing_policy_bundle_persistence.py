import json

import pandas as pd

from riskbands import RiskBands
from riskbands.reporting import load_bundle, load_bundle_metadata
from tests.test_missing_values_current_behavior import make_categorical_missing_frame, make_numeric_missing_frame


def test_bundle_roundtrip_persists_standard_missing_policy(tmp_path):
    df = make_numeric_missing_frame()
    binner = RiskBands(missing_policy="standard", max_bins=3, min_event_rate_diff=0.0).fit(
        df,
        y="target",
        column="score",
    )

    binner.export_bundle(tmp_path / "bundle")
    loaded = load_bundle(tmp_path / "bundle")

    assert loaded["missing_policy"] == "standard"
    assert loaded["effective_missing_policy"] == "standard"
    assert loaded["missing_decision_log"]


def test_bundle_roundtrip_persists_separate_bin_missing_audit(tmp_path):
    df = make_categorical_missing_frame()
    binner = RiskBands(
        missing_policy="separate_bin",
        force_categorical=["grade"],
        max_bins=4,
        min_event_rate_diff=0.0,
    ).fit(df, y="target", column="grade", validate=True)

    binner.export_bundle(tmp_path / "bundle")
    loaded = load_bundle(tmp_path / "bundle")

    assert loaded["missing_policy"] == "separate_bin"
    assert loaded["effective_missing_policy"] == "separate_bin"
    assert loaded["missing_profile"][0]["bin_label"] == "Missing"
    assert loaded["missing_decision_log"][0]["action"] == "separate_bin_created"
    assert (tmp_path / "bundle" / "missing_profile.csv").exists()
    assert (tmp_path / "bundle" / "missing_decision_log.csv").exists()


def test_bundle_roundtrip_persists_forbid_without_missing(tmp_path):
    df = pd.DataFrame({"score": [1.0, 2.0, 3.0, 4.0] * 8, "target": [0, 0, 1, 1] * 8})
    binner = RiskBands(missing_policy="forbid", max_bins=2, min_event_rate_diff=0.0).fit(
        df,
        y="target",
        column="score",
    )

    binner.export_bundle(tmp_path / "bundle")
    loaded = load_bundle_metadata(tmp_path / "bundle")

    assert loaded["missing_policy"] == "forbid"
    assert loaded["missing_profile"] == []
    assert loaded["missing_decision_log"][0]["action"] == "no_missing_detected"


def test_old_bundle_without_missing_fields_loads_as_standard(tmp_path):
    bundle_dir = tmp_path / "old_bundle"
    bundle_dir.mkdir()
    (bundle_dir / "metadata.json").write_text(
        json.dumps({"artifact_type": "riskbands_audit_bundle", "artifact_version": "1.0", "metadata": {}}),
        encoding="utf-8",
    )

    loaded = load_bundle_metadata(bundle_dir)

    assert loaded["missing_policy"] == "standard"
    assert loaded["effective_missing_policy"] == "standard"
    assert loaded["missing_profile"] is None
    assert loaded["missing_decision_log"] is None


def test_old_bundle_with_legacy_missing_policy_loads_as_standard(tmp_path):
    bundle_dir = tmp_path / "old_bundle"
    bundle_dir.mkdir()
    (bundle_dir / "metadata.json").write_text(
        json.dumps(
            {
                "artifact_type": "riskbands_audit_bundle",
                "artifact_version": "1.0",
                "missing_policy": "legacy",
                "effective_missing_policy": "legacy",
                "metadata": {"missing_policy": "legacy"},
            }
        ),
        encoding="utf-8",
    )

    loaded = load_bundle_metadata(bundle_dir)

    assert loaded["missing_policy"] == "standard"
    assert loaded["effective_missing_policy"] == "standard"
    assert loaded["metadata"]["missing_policy"] == "standard"
