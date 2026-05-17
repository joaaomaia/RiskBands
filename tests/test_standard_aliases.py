import json

import pandas as pd

from riskbands import Binner
from riskbands.objectives import resolve_score_strategy, score_objective_components
from riskbands.reporting import load_bundle_metadata


def test_score_strategy_standard_is_canonical_default():
    binner = Binner()

    assert binner.score_strategy == "standard"
    assert binner.get_params()["score_strategy"] == "standard"
    assert resolve_score_strategy(score_strategy="standard") == "standard"
    assert score_objective_components({"iv": 0.1})["score_strategy"] == "standard"


def test_score_strategy_legacy_is_compatibility_alias():
    binner = Binner(score_strategy="legacy")

    assert binner.score_strategy == "standard"
    assert binner.get_params()["score_strategy"] == "standard"
    assert resolve_score_strategy(score_strategy="legacy") == "standard"


def test_set_params_normalizes_legacy_score_strategy_alias():
    binner = Binner(score_strategy="stable")

    binner.set_params(score_strategy="legacy")

    assert binner.score_strategy == "standard"


def test_new_bundle_exports_standard_score_strategy(tmp_path):
    df = pd.DataFrame({"score": [-2, -1, 0, 1, 2, 3] * 10, "target": [0, 0, 0, 1, 1, 1] * 10})
    binner = Binner(max_bins=3, min_event_rate_diff=0.0, score_strategy="legacy")
    binner.fit(df, y="target", column="score")

    binner.export_bundle(tmp_path / "bundle")
    loaded = load_bundle_metadata(tmp_path / "bundle")

    assert loaded["metadata"]["score_strategy"] == "standard"


def test_derived_standard_objective_source_uses_public_standard_name():
    df = pd.DataFrame({"score": [-2, -1, 0, 1, 2, 3] * 10, "target": [0, 0, 0, 1, 1, 1] * 10})
    X = df[["score"]]
    y = df["target"]
    binner = Binner(max_bins=3, min_event_rate_diff=0.0, score_strategy="legacy").fit(
        X,
        y=y,
        column="score",
    )
    binner.objective_summary_ = None
    binner.objective_summaries_ = None

    report = binner.variable_audit_report(X, y)

    assert report.iloc[0]["score_strategy"] == "standard"
    assert report.iloc[0]["objective_source"] == "derived_standard_objective"
    assert "derived_legacy_objective" not in set(report["objective_source"])


def test_old_bundle_score_strategy_legacy_loads_as_standard(tmp_path):
    bundle_dir = tmp_path / "old_bundle"
    bundle_dir.mkdir()
    (bundle_dir / "metadata.json").write_text(
        json.dumps(
            {
                "artifact_type": "riskbands_audit_bundle",
                "artifact_version": "1.0",
                "metadata": {"score_strategy": "legacy"},
            }
        ),
        encoding="utf-8",
    )

    loaded = load_bundle_metadata(bundle_dir)

    assert loaded["metadata"]["score_strategy"] == "standard"
