import pandas as pd

from riskbands.reporting import load_bundle
from tests.test_missing_values_current_behavior import fit_numeric_missing_binner


def _missing_rows(records):
    frame = pd.DataFrame(records)
    return frame.loc[frame["is_missing_bin"]]


def test_bundle_roundtrip_preserves_existing_numeric_missing_profiles(tmp_path):
    binner, _ = fit_numeric_missing_binner(validate=True)
    app = pd.DataFrame(
        {
            "score": [float("nan"), -5.0, 0.0, 4.0, float("nan"), 2.0],
            "target": [1, 0, 0, 1, 0, 1],
        }
    )
    binner.transform(app, column="score", validate=True)

    bundle_dir = tmp_path / "bundle"
    binner.export_bundle(bundle_dir)
    loaded = load_bundle(bundle_dir)
    manifest = loaded["manifest"]

    fit_missing = _missing_rows(manifest["fit_profile"])
    reference_missing = _missing_rows(manifest["reference_profile"])
    application_missing = _missing_rows(manifest["application_profile"])

    assert len(fit_missing) == 1
    assert len(reference_missing) == 1
    assert len(application_missing) == 1
    assert fit_missing.iloc[0]["bin_label"] == "Missing"
    assert application_missing.iloc[0]["bin_label"] == "Missing"
    assert manifest["fit_validation_report"]["validation_type"] == "fit"
    assert manifest["transform_validation_report"]["validation_type"] == "transform"
    assert manifest["validation_report"]["validation_type"] == "transform"


def test_bundle_has_no_dedicated_missing_policy_schema_current_behavior(tmp_path):
    binner, _ = fit_numeric_missing_binner(validate=True)
    bundle_dir = tmp_path / "bundle"

    binner.export_bundle(bundle_dir)
    loaded = load_bundle(bundle_dir)
    manifest = loaded["manifest"]
    metadata = manifest["metadata"]

    for key in ("missing_policy", "effective_missing_policy", "missing_decision_log", "missing_profile"):
        assert key not in manifest
        assert key not in metadata


def test_exporting_bundle_does_not_change_numeric_missing_transform_behavior(tmp_path):
    binner, _ = fit_numeric_missing_binner(validate=True)
    probe = pd.DataFrame({"score": [float("nan"), -5.0]})
    before = binner.transform(probe)

    binner.export_bundle(tmp_path / "bundle")
    after = binner.transform(probe)

    assert before.equals(after)
    assert before.loc[0, "score"] == "Missing"
