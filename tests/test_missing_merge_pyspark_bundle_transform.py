from collections import Counter

import pandas as pd
import pytest

from riskbands import RiskBands
from riskbands.reporting import load_bundle
from tests.test_missing_merge_nearest_event_rate_pandas import fit_numeric_merge
from tests.test_missing_merge_nearest_woe_pandas import fit_numeric_woe_merge

pytestmark = pytest.mark.spark
pytest_plugins = ["tests.test_missing_values_pyspark_current_behavior"]


def _numeric_spark_frame(spark_session, rows):
    from pyspark.sql import types as T

    schema = T.StructType(
        [
            T.StructField("score", T.DoubleType(), True),
            T.StructField("target", T.IntegerType(), True),
        ]
    )
    return spark_session.createDataFrame(rows, schema=schema)


def _values(spark_df):
    return [row["score"] for row in spark_df.select("score").collect()]


@pytest.mark.parametrize(
    "fit_factory",
    [
        fit_numeric_merge,
        fit_numeric_woe_merge,
    ],
)
def test_bundle_load_preserves_merge_decision_and_model_transforms_spark(
    spark_session,
    tmp_path,
    fit_factory,
):
    binner, _ = fit_factory()
    learned_label = binner.missing_merge_map_["score"]
    binner.export_bundle(tmp_path / "bundle")

    loaded = load_bundle(tmp_path / "bundle")
    transformed = binner.transform(
        _numeric_spark_frame(spark_session, [(None, 0), (float("nan"), 1), (-5.0, 0)]),
        column="score",
    )
    observed = _values(transformed)

    assert loaded["missing_policy"] == "merge"
    assert loaded["missing_merge_criterion"] == binner.missing_merge_criterion
    assert loaded["missing_merge_fallback"] == binner.missing_merge_fallback
    assert loaded["missing_merge_map"]["score"] == learned_label
    assert loaded["missing_profile"]
    assert loaded["missing_decision_log"]
    assert loaded["missing_merge_candidates"]
    assert loaded["missing_decision_log"][0]["selected_bin_label"] == learned_label
    assert transformed.__class__.__module__.startswith("pyspark")
    assert Counter(observed)[learned_label] >= 2
    assert "Missing" not in observed


def test_bundle_load_preserves_merge_fallback_and_model_transforms_spark(spark_session, tmp_path):
    fit_df = pd.DataFrame({"score": [-5.0, -4.0, 0.0, 3.0, 5.0] * 8, "target": [0, 0, 1, 1, 1] * 8})
    binner = RiskBands(
        max_bins=3,
        min_event_rate_diff=0.0,
        missing_policy="merge",
        missing_merge_criterion="nearest_event_rate",
        missing_merge_fallback="separate_bin",
    ).fit(fit_df, y="target", column="score")
    binner.export_bundle(tmp_path / "bundle")

    loaded = load_bundle(tmp_path / "bundle")
    transformed = binner.transform(
        _numeric_spark_frame(spark_session, [(None, 0), (float("nan"), 1), (-5.0, 0)]),
        column="score",
    )

    assert loaded["missing_merge_fallback"] == "separate_bin"
    assert loaded["missing_merge_map"] == {}
    assert loaded["missing_decision_log"]
    assert loaded["missing_decision_log"][0]["action"] == "no_missing_detected"
    assert transformed.__class__.__module__.startswith("pyspark")
    assert Counter(_values(transformed))["Missing"] == 2


def test_bundle_load_then_spark_raise_fallback_records_transform_log(spark_session, tmp_path):
    fit_df = pd.DataFrame({"score": [-5.0, -4.0, 0.0, 3.0, 5.0] * 8, "target": [0, 0, 1, 1, 1] * 8})
    binner = RiskBands(
        max_bins=3,
        min_event_rate_diff=0.0,
        missing_policy="merge",
        missing_merge_criterion="nearest_event_rate",
        missing_merge_fallback="raise",
    ).fit(fit_df, y="target", column="score")
    binner.export_bundle(tmp_path / "before_transform")
    loaded_before = load_bundle(tmp_path / "before_transform")

    assert loaded_before["missing_merge_fallback"] == "raise"
    assert loaded_before["missing_merge_map"] == {}

    with pytest.raises(ValueError, match="no merge decision was learned"):
        binner.transform(
            _numeric_spark_frame(spark_session, [(None, 0), (-5.0, 0)]),
            column="score",
        )

    assert binner.missing_transform_fallback_log_ is not None
    assert not binner.missing_transform_fallback_log_.empty
    assert binner.missing_transform_fallback_log_.iloc[0]["backend"] == "pyspark"

    binner.export_bundle(tmp_path / "after_transform")
    loaded_after = load_bundle(tmp_path / "after_transform")

    assert loaded_after["missing_transform_fallback_log"]
    assert loaded_after["missing_transform_fallback_log"][0]["backend"] == "pyspark"


def test_bundle_model_still_blocks_spark_return_woe(spark_session, tmp_path):
    binner, _ = fit_numeric_merge()
    binner.export_bundle(tmp_path / "bundle")
    loaded = load_bundle(tmp_path / "bundle")

    assert loaded["missing_merge_map"] == binner.missing_merge_map_
    with pytest.raises(NotImplementedError, match="return_woe=False"):
        binner.transform(
            _numeric_spark_frame(spark_session, [(None, 0), (1.0, 1)]),
            column="score",
            return_woe=True,
        )
