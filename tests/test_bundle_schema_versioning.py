import json

import numpy as np
import pandas as pd

from riskbands import Binner
from riskbands.reporting import BUNDLE_SCHEMA_VERSION, load_bundle_metadata


def make_frame(n=120, seed=31):
    rng = np.random.default_rng(seed)
    score = rng.normal(size=n)
    target = (score + rng.normal(scale=0.4, size=n) > 0).astype(int)
    return pd.DataFrame({"score": score, "target": target})


def test_new_bundle_contains_schema_version_and_keeps_legacy_fields(tmp_path):
    df = make_frame()
    binner = Binner(strategy="supervised", max_bins=3, min_event_rate_diff=0.0)
    binner.fit(df, y="target", column="score")

    bundle_dir = tmp_path / "bundle"
    binner.export_bundle(bundle_dir)

    manifest = json.loads((bundle_dir / "metadata.json").read_text(encoding="utf-8"))
    binnings = json.loads((bundle_dir / "binnings.json").read_text(encoding="utf-8"))

    assert manifest["artifact_type"] == "riskbands_audit_bundle"
    assert manifest["artifact_version"] == "1.0"
    assert manifest["bundle_schema_version"] == BUNDLE_SCHEMA_VERSION
    assert "riskbands_version" in manifest
    assert "metadata" in manifest
    assert "artifacts" in manifest

    assert binnings["artifact_type"] == "riskbands_binning_bundle"
    assert binnings["artifact_version"] == "1.0"
    assert binnings["bundle_schema_version"] == BUNDLE_SCHEMA_VERSION
    assert "riskbands_version" in binnings
    assert "metadata" in binnings
    assert "features" in binnings

    loaded = load_bundle_metadata(bundle_dir)
    assert loaded["bundle_schema_version"] == BUNDLE_SCHEMA_VERSION
    assert loaded["riskbands_version"] == manifest["riskbands_version"]


def test_legacy_bundle_without_schema_version_loads(tmp_path):
    bundle_dir = tmp_path / "legacy_bundle"
    bundle_dir.mkdir()
    legacy_manifest = {
        "artifact_type": "riskbands_audit_bundle",
        "artifact_version": "1.0",
        "riskbands_version": "2.0.3",
        "metadata": {"features": ["score"]},
        "artifacts": {"summary_csv": "summary.csv"},
    }
    (bundle_dir / "metadata.json").write_text(
        json.dumps(legacy_manifest),
        encoding="utf-8",
    )

    loaded = load_bundle_metadata(bundle_dir)

    assert loaded["bundle_schema_version"] == "1.0"
    assert loaded["riskbands_version"] == "2.0.3"
    assert loaded["fit_profile"] is None
    assert loaded["reference_profile"] is None
    assert loaded["validation_report"] is None


def test_missing_new_profile_fields_do_not_affect_transform():
    df = make_frame()
    binner = Binner(strategy="supervised", max_bins=3, min_event_rate_diff=0.0)
    binner.fit(df, y="target", column="score")

    transformed = binner.transform(df[["score"]])

    assert transformed.shape == (len(df), 1)
    assert list(transformed.columns) == ["score"]
    assert not transformed.isna().any().any()
