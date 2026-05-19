import json

import numpy as np
import pandas as pd

from riskbands import RiskBands
from riskbands.reporting import load_bundle, load_bundle_metadata
from tests.test_missing_merge_nearest_event_rate_pandas import (
    fit_numeric_merge,
    make_categorical_event_rate_frame,
)


def test_bundle_roundtrip_persists_merge_numeric_decision(tmp_path):
    binner, _ = fit_numeric_merge()
    bundle_dir = tmp_path / "bundle"

    binner.export_bundle(bundle_dir)
    loaded = load_bundle(bundle_dir)

    assert loaded["missing_policy"] == "merge"
    assert loaded["effective_missing_policy"] == "merge"
    assert loaded["missing_merge_criterion"] == "nearest_event_rate"
    assert loaded["missing_merge_fallback"] == "separate_bin"
    assert loaded["missing_profile"][0]["bin_label"] == "Missing"
    assert loaded["missing_profile"][0]["merge_status"] == "merged"
    assert loaded["missing_decision_log"][0]["action"] == "missing_merged"
    assert loaded["missing_decision_log"][0]["candidate_bins"]
    assert loaded["missing_merge_candidates"]
    assert loaded["missing_merge_map"] == binner.missing_merge_map_
    assert (bundle_dir / "missing_profile.csv").exists()
    assert (bundle_dir / "missing_decision_log.csv").exists()
    assert (bundle_dir / "missing_merge_candidates.csv").exists()


def test_bundle_roundtrip_persists_merge_categorical_decision(tmp_path):
    df = make_categorical_event_rate_frame()
    binner = RiskBands(
        max_bins=3,
        min_event_rate_diff=0.0,
        force_categorical=["rating"],
        missing_policy="merge",
        missing_merge_criterion="nearest_event_rate",
    ).fit(df, y="target", column="rating")

    binner.export_bundle(tmp_path / "bundle")
    loaded = load_bundle(tmp_path / "bundle")

    assert loaded["missing_policy"] == "merge"
    assert loaded["missing_decision_log"][0]["variable"] == "rating"
    assert loaded["missing_decision_log"][0]["selected_bin_label"] == binner.missing_decision_log_.iloc[0][
        "selected_bin_label"
    ]
    assert loaded["missing_merge_map"] == binner.missing_merge_map_


def test_transform_after_bundle_export_still_uses_learned_merge_decision(tmp_path):
    binner, _ = fit_numeric_merge()
    learned_destination = binner.missing_decision_log_.iloc[0]["selected_bin_label"]
    before = binner.transform(pd.DataFrame({"score": [np.nan, -5.0]}))

    binner.export_bundle(tmp_path / "bundle")
    loaded = load_bundle(tmp_path / "bundle")
    after = binner.transform(pd.DataFrame({"score": [np.nan, -5.0]}))

    assert before.equals(after)
    assert after.loc[0, "score"] == learned_destination
    assert loaded["missing_merge_map"]["score"] == learned_destination


def test_bundle_roundtrip_persists_missing_merge_fallback_for_no_fit_missing(tmp_path):
    df = pd.DataFrame({"score": [-5.0, -4.0, 0.0, 4.0, 5.0] * 8, "target": [0, 0, 1, 1, 1] * 8})
    binner = RiskBands(
        max_bins=3,
        min_event_rate_diff=0.0,
        missing_policy="merge",
        missing_merge_criterion="nearest_event_rate",
        missing_merge_fallback="raise",
    ).fit(df, y="target", column="score")

    binner.export_bundle(tmp_path / "bundle")
    loaded = load_bundle(tmp_path / "bundle")

    assert loaded["missing_policy"] == "merge"
    assert loaded["missing_merge_fallback"] == "raise"
    assert loaded["missing_merge_map"] == {}
    assert loaded["missing_decision_log"][0]["action"] == "no_missing_detected"


def test_old_bundle_without_missing_merge_fields_loads_with_none_values(tmp_path):
    bundle_dir = tmp_path / "old_bundle"
    bundle_dir.mkdir()
    (bundle_dir / "metadata.json").write_text(
        json.dumps(
            {
                "artifact_type": "riskbands_audit_bundle",
                "artifact_version": "1.0",
                "metadata": {"missing_policy": "legacy"},
            }
        ),
        encoding="utf-8",
    )

    loaded = load_bundle_metadata(bundle_dir)

    assert loaded["missing_policy"] == "standard"
    assert loaded["effective_missing_policy"] == "standard"
    assert loaded["metadata"]["missing_policy"] == "standard"
    assert loaded["missing_merge_criterion"] is None
    assert loaded["missing_merge_fallback"] is None
    assert loaded["missing_merge_candidates"] is None
    assert loaded["missing_merge_map"] is None


def test_standard_separate_bin_and_forbid_bundle_fields_remain_compatible(tmp_path):
    standard = RiskBands(missing_policy="standard", max_bins=2, min_event_rate_diff=0.0).fit(
        pd.DataFrame({"score": [1.0, 2.0, np.nan, 4.0], "target": [0, 1, 0, 1]}),
        y="target",
        column="score",
    )
    separate = RiskBands(missing_policy="separate_bin", max_bins=2, min_event_rate_diff=0.0).fit(
        pd.DataFrame({"score": [1.0, 2.0, np.nan, 4.0], "target": [0, 1, 0, 1]}),
        y="target",
        column="score",
    )
    forbid = RiskBands(missing_policy="forbid", max_bins=2, min_event_rate_diff=0.0).fit(
        pd.DataFrame({"score": [1.0, 2.0, 3.0, 4.0], "target": [0, 1, 0, 1]}),
        y="target",
        column="score",
    )

    for name, binner in [("standard", standard), ("separate", separate), ("forbid", forbid)]:
        binner.export_bundle(tmp_path / name)
        loaded = load_bundle(tmp_path / name)
        assert loaded["missing_policy"] == binner.missing_policy
        assert loaded["missing_merge_criterion"] is None
        assert loaded["missing_merge_candidates"] in (None, [])
