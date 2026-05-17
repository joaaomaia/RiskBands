import json

import pandas as pd

from riskbands import RiskBands
from riskbands.reporting import BUNDLE_SCHEMA_VERSION, load_bundle
from tests.test_fit_validate_true import make_frame


def fit_validated_binner():
    df = make_frame()
    binner = RiskBands(strategy="supervised", max_bins=4, min_event_rate_diff=0.0)
    binner.fit(df, y="target", column="score", validate=True)
    binner.transform(df[["score", "target"]], validate=True)
    return binner, df


def test_new_bundle_loads_with_profiles_reports_and_schema(tmp_path):
    binner, _ = fit_validated_binner()
    bundle_dir = tmp_path / "bundle"
    binner.export_bundle(bundle_dir)

    loaded = load_bundle(bundle_dir)
    manifest = loaded["manifest"]

    assert loaded["bundle_schema_version"] == BUNDLE_SCHEMA_VERSION
    assert loaded["binnings"] is not None
    assert manifest["fit_profile"] is not None
    assert manifest["reference_profile"] is not None
    assert manifest["reference_profile_source"] == "fit_profile"
    assert manifest["fit_validation_report"] is not None
    assert manifest["transform_validation_report"] is not None
    assert manifest["validation_report"] is not None
    assert manifest["data_schema"] is not None
    assert manifest["metadata"]["sampling_metadata"]["sampling_applied"] is False
    assert manifest["metadata"]["sampling_metadata"]["sampling_strategy"] == "none"
    assert loaded["fit_validation_report"] is not None
    assert loaded["transform_validation_report"] is not None
    assert loaded["manifest"]["metadata"]["sampling_metadata"] == manifest["metadata"]["sampling_metadata"]


def test_bundle_binnings_are_preserved_on_load(tmp_path):
    binner, _ = fit_validated_binner()
    bundle_dir = tmp_path / "bundle"
    binner.export_bundle(bundle_dir)

    raw_binnings = json.loads((bundle_dir / "binnings.json").read_text(encoding="utf-8"))
    loaded = load_bundle(bundle_dir)

    assert loaded["binnings"]["artifact_type"] == "riskbands_binning_bundle"
    assert loaded["binnings"]["features"] == raw_binnings["features"]


def test_bundle_without_source_profile_or_validation_report_loads(tmp_path):
    df = make_frame()
    binner = RiskBands(strategy="supervised", max_bins=4, min_event_rate_diff=0.0)
    binner.fit(df, y="target", column="score", validate=False)
    bundle_dir = tmp_path / "bundle"
    binner.export_bundle(bundle_dir)

    loaded = load_bundle(bundle_dir)

    assert loaded["source_profile"] is None
    assert loaded["fit_validation_report"] is None
    assert loaded["transform_validation_report"] is None
    assert loaded["validation_report"] is None
    assert loaded["reference_profile"] is not None


def test_old_bundle_loads_without_new_profile_fields(tmp_path):
    bundle_dir = tmp_path / "legacy_bundle"
    bundle_dir.mkdir()
    (bundle_dir / "metadata.json").write_text(
        json.dumps(
            {
                "artifact_type": "riskbands_audit_bundle",
                "artifact_version": "1.0",
                "riskbands_version": "2.0.3",
                "metadata": {"features": ["score"]},
                "artifacts": {},
            }
        ),
        encoding="utf-8",
    )

    loaded = load_bundle(bundle_dir)

    assert loaded["manifest"]["bundle_schema_version"] == "1.0"
    assert loaded["reference_profile"] is None
    assert loaded["reference_profile_source"] == "missing"


def test_transform_validate_true_after_loading_reference_from_bundle(tmp_path):
    binner, df = fit_validated_binner()
    bundle_dir = tmp_path / "bundle"
    binner.export_bundle(bundle_dir)
    loaded = load_bundle(bundle_dir)
    binner.reference_profile_ = pd.DataFrame(loaded["reference_profile"])
    binner.reference_profile_source_ = loaded["reference_profile_source"]

    transformed = binner.transform(df[["score", "target"]], validate=True)

    assert isinstance(transformed, pd.DataFrame)
    assert binner.validation_report_["validation_type"] == "transform"
    assert binner.application_profile_ is not None
