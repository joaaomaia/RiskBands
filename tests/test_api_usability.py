from __future__ import annotations

from pathlib import Path
import json

import numpy as np
import pandas as pd
import pytest

from riskbands import Binner


@pytest.fixture()
def demo_df() -> pd.DataFrame:
    rng = np.random.default_rng(17)
    n = 420
    df = pd.DataFrame(
        {
            "age": rng.normal(loc=35, scale=9, size=n),
            "income": rng.normal(loc=5200, scale=900, size=n),
            "segment": rng.choice(["A", "B", "C"], size=n, p=[0.45, 0.35, 0.20]),
            "month": rng.choice([202301, 202302, 202303, 202304], size=n),
        }
    )
    logits = (
        -0.25
        + 0.09 * (df["age"] - 35)
        - 0.00025 * (df["income"] - 5200)
        + 0.18 * (df["segment"] == "C").astype(float)
        + 0.04 * (df["month"] - 202301)
    )
    prob = 1.0 / (1.0 + np.exp(-logits))
    df["target"] = (rng.random(n) < prob).astype(int)
    return df


def test_dataframe_first_fit_populates_friendly_cached_artifacts(demo_df: pd.DataFrame):
    binner = Binner(
        strategy="supervised",
        max_n_bins=5,
        check_stability=True,
        score_strategy="stable",
    )

    binner.fit(demo_df, y="target", column="age", time_col="month")

    assert binner.feature_name_ == "age"
    assert binner.target_name_ == "target"
    assert binner.n_features_in_ == 1
    assert not binner.binning_table_.empty
    assert not binner.summary_.empty
    assert not binner.report_.empty
    assert not binner.score_details_.empty
    assert not binner.diagnostics_.empty
    assert isinstance(binner.score_, float)
    assert isinstance(binner.comparison_score_, float)
    assert {"variable", "objective_score", "objective_preference_score"} <= set(binner.score_details_.columns)
    assert binner.metadata_["score_strategy"] == "stable"


def test_series_fit_transform_returns_series_and_preserves_index(demo_df: pd.DataFrame):
    binner = Binner(strategy="supervised", max_bins=4, score_strategy="stable")

    transformed = binner.fit_transform(demo_df["age"], y=demo_df["target"])

    assert isinstance(transformed, pd.Series)
    assert transformed.name == "age"
    assert transformed.index.equals(demo_df.index)
    assert isinstance(binner.score_, float)


def test_transform_supports_series_return_type_for_single_selected_column(demo_df: pd.DataFrame):
    binner = Binner(strategy="supervised", max_bins=4)
    binner.fit(demo_df, y="target", columns=["age", "income"], time_col="month")

    transformed = binner.transform(demo_df[["age"]], column="age", return_type="series")

    assert isinstance(transformed, pd.Series)
    assert transformed.name == "age"
    assert transformed.index.equals(demo_df.index)


def test_transform_keeps_dataframe_shape_and_index_for_dataframe_inputs(demo_df: pd.DataFrame):
    binner = Binner(strategy="supervised", max_bins=4)
    binner.fit(demo_df, y="target", columns=["age", "income"], time_col="month")

    transformed = binner.transform(demo_df[["age", "income"]])

    assert isinstance(transformed, pd.DataFrame)
    assert transformed.columns.tolist() == ["age", "income"]
    assert transformed.index.equals(demo_df.index)


def test_get_params_and_set_params_sync_sklearn_style_aliases():
    binner = Binner(
        max_bins=4,
        monotonic="ascending",
        score_strategy="stable",
        score_weights={"psi_weight": 0.22},
    )

    params = binner.get_params()

    assert params["max_bins"] == 4
    assert params["max_n_bins"] == 4
    assert params["monotonic"] == "ascending"
    assert params["monotonic_trend"] == "ascending"
    assert params["score_strategy"] == "stable"

    binner.set_params(max_n_bins=6, monotonic_trend="descending", woe_shrinkage_strength=10.0)

    assert binner.max_bins == 6
    assert binner.max_n_bins == 6
    assert binner.monotonic == "descending"
    assert binner.monotonic_trend == "descending"
    assert binner.woe_shrinkage_strength == 10.0


def test_summary_report_and_diagnostics_methods_are_friendly_aliases(demo_df: pd.DataFrame):
    binner = Binner(strategy="supervised", check_stability=True, score_strategy="legacy")
    binner.fit(demo_df, y="target", column="age", time_col="month")

    summary = binner.summary()
    report = binner.report()
    diagnostics = binner.diagnostics(kind="bin")
    variable_diagnostics = binner.diagnostics(kind="variable")

    assert not summary.empty
    assert not report.empty
    assert not diagnostics.empty
    assert not variable_diagnostics.empty
    assert report.iloc[0]["score_strategy"] == "legacy"
    assert summary.iloc[0]["score_strategy"] == "legacy"


def test_score_table_audit_table_and_metadata_expose_effective_weights(demo_df: pd.DataFrame):
    binner = Binner(
        strategy="supervised",
        check_stability=True,
        score_strategy="stable",
        score_weights={
            "temporal_variance_weight": 0.30,
            "window_drift_weight": 0.10,
            "rank_inversion_weight": 0.15,
            "separation_weight": 0.20,
            "entropy_weight": 0.10,
            "psi_weight": 0.15,
        },
    )
    binner.fit(demo_df, y="target", column="age", time_col="month")

    score_table = binner.score_table()
    audit_table = binner.audit_table()

    assert not score_table.empty
    assert not audit_table.empty
    assert "weight_profile" in score_table.columns
    assert "temporal_variance_weight" in score_table.iloc[0]["weight_profile"]
    assert "objective_weight_temporal_variance_weight" in score_table.columns
    assert "weight_profile" in audit_table.columns
    assert "score_weights_input" in binner.metadata_
    assert binner.metadata_["score_weights_input"]["temporal_variance_weight"] == 0.30
    assert "score_weights" in binner.metadata_
    assert "temporal_variance_weight" in binner.metadata_["score_weights"]


def test_feature_binning_table_aliases_match_primary_method(demo_df: pd.DataFrame):
    binner = Binner(strategy="supervised", max_bins=4)
    binner.fit(demo_df, y="target", columns=["age", "income"])

    base = binner.binning_table(column="age")
    assert base.equals(binner.feature_binning_table(column="age"))
    assert base.equals(binner.get_binning_table(column="age"))


def test_diagnostics_requires_time_col_when_no_temporal_context_is_available(demo_df: pd.DataFrame):
    binner = Binner(strategy="supervised")
    binner.fit(demo_df, y="target", column="age")

    with pytest.raises(ValueError, match="Temporal diagnostics require `time_col`"):
        binner.diagnostics(refresh=True)


def test_missing_target_column_raises_helpful_error(demo_df: pd.DataFrame):
    df = demo_df.drop(columns=["target"])
    with pytest.raises(KeyError, match="Target column 'target' was not found in `X`"):
        Binner().fit(df, y="target", column="age")


def test_plotly_notebook_exists_and_references_the_friendly_api():
    notebook_path = Path("examples/riskbands_synthetic_plotly_comparative_demo.ipynb")
    payload = json.loads(notebook_path.read_text(encoding="utf-8"))
    text = "\n".join(
        "".join(cell.get("source", []))
        for cell in payload.get("cells", [])
    )

    assert notebook_path.exists()
    assert "plotly" in text.lower()
    assert "Binner" in text
    assert "fit(" in text
    assert "summary()" in text
    assert "stable" in text
    assert "legacy" in text
