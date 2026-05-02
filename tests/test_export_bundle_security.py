import json
from pathlib import Path

import numpy as np
import pandas as pd

from riskbands import Binner


def assert_path_inside(base: Path, candidate: Path):
    base_resolved = base.resolve()
    candidate_resolved = candidate.resolve()
    assert candidate_resolved == base_resolved or base_resolved in candidate_resolved.parents


def read_bundle_metadata(bundle_dir):
    return json.loads((bundle_dir / "metadata.json").read_text(encoding="utf-8"))


def make_numeric_credit_frame(features, n=120, seed=7):
    rng = np.random.default_rng(seed)
    data = {feature: rng.normal(size=n) for feature in features}
    combined_signal = sum(data[feature] for feature in features)
    target = (combined_signal + rng.normal(scale=0.35, size=n) > 0).astype(int)
    data["target"] = target
    return pd.DataFrame(data)


def test_export_bundle_does_not_write_feature_table_outside_bundle(tmp_path):
    rng = np.random.default_rng(11)
    n = 100
    malicious_feature = "../../outside_bundle"
    values = rng.normal(size=n)
    target = (values + rng.normal(scale=0.25, size=n) > 0).astype(int)
    df = pd.DataFrame(
        {
            malicious_feature: values,
            "target": target,
        }
    )
    bundle_dir = tmp_path / "bundle"
    outside_file = tmp_path / "outside_bundle.csv"
    binner = Binner(strategy="supervised", max_bins=3, min_event_rate_diff=0.0)

    binner.fit(df, y="target", column=malicious_feature)
    binner.export_bundle(bundle_dir)

    assert bundle_dir.exists()
    assert (bundle_dir / "metadata.json").exists()
    assert not outside_file.exists()

    metadata = read_bundle_metadata(bundle_dir)
    feature_tables = metadata["artifacts"]["feature_tables"]

    assert feature_tables

    for original_feature, relative_path in feature_tables.items():
        path = Path(relative_path)

        assert original_feature == malicious_feature
        assert not path.is_absolute()
        assert ".." not in path.parts
        assert "/" not in path.name
        assert "\\" not in path.name

        resolved_path = bundle_dir / path
        assert_path_inside(bundle_dir, resolved_path)
        assert resolved_path.exists()


def test_export_bundle_sanitizes_feature_names_with_path_separators(tmp_path):
    features = ["feature/with/slash", r"feature\with\backslash"]
    df = make_numeric_credit_frame(features, seed=19)
    bundle_dir = tmp_path / "bundle"
    feature_tables_dir = bundle_dir / "feature_tables"
    binner = Binner(strategy="supervised", max_bins=3, min_event_rate_diff=0.0)

    binner.fit(df, y="target", columns=features)
    binner.export_bundle(bundle_dir)

    metadata = read_bundle_metadata(bundle_dir)
    feature_tables = metadata["artifacts"]["feature_tables"]

    assert set(feature_tables) == set(features)

    for relative_path in feature_tables.values():
        path = Path(relative_path)

        assert path.parts[0] == "feature_tables"
        assert not path.is_absolute()
        assert ".." not in path.parts

        resolved_path = bundle_dir / path
        assert_path_inside(bundle_dir, resolved_path)

        assert resolved_path.parent == feature_tables_dir
        assert resolved_path.exists()
        assert "/" not in resolved_path.name
        assert "\\" not in resolved_path.name


def test_export_bundle_handles_sanitized_feature_name_collisions(tmp_path):
    features = ["feature/a", "feature:a", "feature a"]
    df = make_numeric_credit_frame(features, seed=23)
    bundle_dir = tmp_path / "bundle"
    binner = Binner(strategy="supervised", max_bins=3, min_event_rate_diff=0.0)

    binner.fit(df, y="target", columns=features)
    binner.export_bundle(bundle_dir)

    metadata = read_bundle_metadata(bundle_dir)
    feature_tables = metadata["artifacts"]["feature_tables"]

    assert set(feature_tables) == set(features)

    paths = list(feature_tables.values())
    assert len(paths) == len(set(paths))

    for relative_path in paths:
        resolved_path = bundle_dir / relative_path
        assert_path_inside(bundle_dir, resolved_path)
        assert resolved_path.exists()
