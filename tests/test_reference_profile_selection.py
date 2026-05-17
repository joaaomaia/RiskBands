import json

from pandas.testing import assert_frame_equal

from riskbands import RiskBands
from riskbands.reporting import load_bundle_metadata
from tests.test_fit_validate_true import ValidatingFakeSparkDataFrame, make_frame, patch_fake_pyspark


def test_reference_profile_uses_fit_profile_when_source_profile_is_missing():
    df = make_frame()
    binner = RiskBands(strategy="supervised", max_bins=4, min_event_rate_diff=0.0)

    binner.fit(df, y="target", column="score")

    assert binner.reference_profile_source_ == "fit_profile"
    assert_frame_equal(binner.reference_profile_, binner.fit_profile_)


def test_reference_profile_uses_source_profile_when_available(monkeypatch):
    patch_fake_pyspark(monkeypatch)
    spark_df = ValidatingFakeSparkDataFrame(make_frame(n=160))
    binner = RiskBands(strategy="supervised", max_bins=3, min_event_rate_diff=0.0, sample_size=60)

    binner.fit(spark_df, target="target", column="score", validate=True)

    assert binner.source_profile_ is not None
    assert binner.reference_profile_source_ == "source_profile"
    assert_frame_equal(binner.reference_profile_, binner.source_profile_)


def test_bundle_new_preserves_reference_profile_and_source(tmp_path):
    df = make_frame()
    binner = RiskBands(strategy="supervised", max_bins=4, min_event_rate_diff=0.0)
    binner.fit(df, y="target", column="score")

    bundle_dir = tmp_path / "bundle"
    binner.export_bundle(bundle_dir)
    manifest = json.loads((bundle_dir / "metadata.json").read_text(encoding="utf-8"))
    loaded = load_bundle_metadata(bundle_dir)

    assert manifest["reference_profile_source"] == "fit_profile"
    assert "reference_profile" in manifest
    assert loaded["reference_profile_source"] == "fit_profile"
    assert loaded["reference_profile"] == manifest["reference_profile"]


def test_legacy_bundle_without_reference_profile_does_not_break(tmp_path):
    bundle_dir = tmp_path / "legacy"
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

    loaded = load_bundle_metadata(bundle_dir)

    assert loaded["reference_profile"] is None
    assert loaded["reference_profile_source"] == "missing"


def test_legacy_bundle_reconstructs_reference_profile_from_fit_profile(tmp_path):
    fit_profile = [
        {
            "variable": "score",
            "bin_label": "(-inf, 0.0)",
            "n": 10,
            "events": 2,
            "event_rate": 0.2,
        }
    ]
    bundle_dir = tmp_path / "legacy_with_fit_profile"
    bundle_dir.mkdir()
    (bundle_dir / "metadata.json").write_text(
        json.dumps(
            {
                "artifact_type": "riskbands_audit_bundle",
                "artifact_version": "1.0",
                "riskbands_version": "2.0.3",
                "metadata": {"features": ["score"]},
                "artifacts": {},
                "fit_profile": fit_profile,
            }
        ),
        encoding="utf-8",
    )

    loaded = load_bundle_metadata(bundle_dir)

    assert loaded["reference_profile"] == fit_profile
    assert loaded["reference_profile_source"] == "fit_profile"


def test_loaded_bundle_exposes_reference_for_future_transform_validation(tmp_path):
    df = make_frame()
    binner = RiskBands(strategy="supervised", max_bins=4, min_event_rate_diff=0.0)
    binner.fit(df, y="target", column="score")
    binner.export_bundle(tmp_path / "bundle")

    loaded = load_bundle_metadata(tmp_path / "bundle")

    assert loaded["reference_profile"] is not None
    assert loaded["reference_profile_source"] in {"fit_profile", "source_profile"}
