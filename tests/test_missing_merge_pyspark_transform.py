from collections import Counter

import pandas as pd
import pytest

from riskbands import RiskBands
from tests.test_missing_merge_nearest_event_rate_pandas import (
    fit_numeric_merge,
    make_categorical_event_rate_frame,
)
from tests.test_missing_merge_nearest_woe_pandas import (
    fit_categorical_woe_merge,
    fit_numeric_woe_merge,
)

pytestmark = pytest.mark.spark
pytest_plugins = ["tests.test_missing_values_pyspark_current_behavior"]

SPARK_MERGE_FIT_MESSAGE = 'missing_policy="merge" with PySpark fit is not implemented'
SPARK_WOE_MESSAGE = "PySpark transform currently supports return_woe=False only"


def _numeric_spark_frame(spark_session, rows):
    from pyspark.sql import types as T

    schema = T.StructType(
        [
            T.StructField("score", T.DoubleType(), True),
            T.StructField("target", T.IntegerType(), True),
        ]
    )
    return spark_session.createDataFrame(rows, schema=schema)


def _categorical_spark_frame(spark_session, rows, *, column="rating"):
    from pyspark.sql import types as T

    schema = T.StructType(
        [
            T.StructField(column, T.StringType(), True),
            T.StructField("target", T.IntegerType(), True),
        ]
    )
    return spark_session.createDataFrame(rows, schema=schema)


def _only_column_values(spark_df, column):
    return [row[column] for row in spark_df.select(column).collect()]


def _single_value(spark_df, column):
    values = _only_column_values(spark_df, column)
    assert len(values) == 1
    return values[0]


@pytest.mark.parametrize(
    "fit_factory",
    [
        fit_numeric_merge,
        fit_numeric_woe_merge,
    ],
)
def test_numeric_merge_pandas_fit_spark_transform_routes_null_and_nan(spark_session, fit_factory):
    binner, _ = fit_factory()
    learned_label = binner.missing_merge_map_["score"]
    sdf = _numeric_spark_frame(spark_session, [(None, 0), (float("nan"), 1), (-5.0, 0)])

    transformed = binner.transform(sdf, column="score")
    observed = _only_column_values(transformed, "score")

    assert transformed.__class__.__module__.startswith("pyspark")
    assert Counter(observed)[learned_label] >= 2
    assert "Missing" not in observed


def test_unsupervised_merge_spark_transform_routes_null_and_nan_to_separate_fallback(spark_session):
    fit_df = pd.DataFrame({"score": [-5.0, -4.0, 0.0, 3.0, 5.0] * 8, "target": [0, 0, 1, 1, 1] * 8})
    binner = RiskBands(
        strategy="unsupervised",
        max_bins=3,
        missing_policy="merge",
        missing_merge_criterion="nearest_event_rate",
        missing_merge_fallback="separate_bin",
    ).fit(fit_df, y="target", column="score")
    sdf = _numeric_spark_frame(spark_session, [(None, 0), (float("nan"), 1), (-5.0, 0)])

    observed = _only_column_values(binner.transform(sdf, column="score"), "score")

    assert binner.missing_merge_map_ == {}
    assert Counter(observed)["Missing"] == 2


def test_unsupervised_merge_spark_transform_applies_existing_merge_map(spark_session):
    fit_df = pd.DataFrame({"score": [-5.0, -4.0, 0.0, 3.0, 5.0] * 8, "target": [0, 0, 1, 1, 1] * 8})
    binner = RiskBands(
        strategy="unsupervised",
        max_bins=3,
        missing_policy="merge",
        missing_merge_criterion="nearest_event_rate",
    ).fit(fit_df, y="target", column="score")
    learned_label = 1.0
    binner.missing_merge_map_["score"] = learned_label
    sdf = _numeric_spark_frame(spark_session, [(None, 0), (float("nan"), 1), (-5.0, 0)])

    observed = _only_column_values(binner.transform(sdf, column="score"), "score")

    assert Counter(observed)[learned_label] >= 2
    assert "Missing" not in observed


def test_unsupervised_merge_spark_transform_raise_fallback_detects_missing(spark_session):
    fit_df = pd.DataFrame({"score": [-5.0, -4.0, 0.0, 3.0, 5.0] * 8, "target": [0, 0, 1, 1, 1] * 8})
    binner = RiskBands(
        strategy="unsupervised",
        max_bins=3,
        missing_policy="merge",
        missing_merge_criterion="nearest_event_rate",
        missing_merge_fallback="raise",
    ).fit(fit_df, y="target", column="score")
    sdf = _numeric_spark_frame(spark_session, [(None, 0), (-5.0, 0)])

    with pytest.raises(
        ValueError,
        match=(
            "missing_policy='merge' detected missing values during Spark transform for feature score, "
            "but no merge decision was learned during fit"
        ),
    ):
        binner.transform(sdf, column="score")


def test_categorical_nearest_event_rate_merge_routes_null_and_keeps_unknown_distinct(spark_session):
    df = make_categorical_event_rate_frame()
    binner = RiskBands(
        max_bins=3,
        min_event_rate_diff=0.0,
        force_categorical=["rating"],
        missing_policy="merge",
        missing_merge_criterion="nearest_event_rate",
    ).fit(df, y="target", column="rating")
    learned_label = binner.missing_merge_map_["rating"]
    expected_unknown = binner.transform(pd.DataFrame({"rating": ["Z"]})).loc[0, "rating"]

    missing_value = _single_value(
        binner.transform(_categorical_spark_frame(spark_session, [(None, 1)]), column="rating"),
        "rating",
    )
    unknown_value = _single_value(
        binner.transform(_categorical_spark_frame(spark_session, [("Z", 0)]), column="rating"),
        "rating",
    )

    assert str(missing_value) == str(learned_label)
    assert str(unknown_value) == str(expected_unknown)
    assert str(unknown_value) != str(missing_value)


def test_categorical_nearest_woe_merge_routes_null_and_keeps_unknown_distinct(spark_session):
    binner, _ = fit_categorical_woe_merge()
    learned_label = binner.missing_merge_map_["rating"]
    expected_unknown = binner.transform(pd.DataFrame({"rating": ["Z"]})).loc[0, "rating"]

    missing_value = _single_value(
        binner.transform(_categorical_spark_frame(spark_session, [(None, 1)]), column="rating"),
        "rating",
    )
    unknown_value = _single_value(
        binner.transform(_categorical_spark_frame(spark_session, [("Z", 0)]), column="rating"),
        "rating",
    )

    assert str(missing_value) == str(learned_label)
    assert str(unknown_value) == str(expected_unknown)
    assert str(unknown_value) != str(missing_value)


def test_merge_spark_fit_still_fails_before_collection(spark_session, monkeypatch):
    sdf = _numeric_spark_frame(spark_session, [(1.0, 0), (None, 1), (3.0, 0), (4.0, 1)])
    from pyspark.sql import DataFrame as SparkDataFrame

    def fail_collect(self, *args, **kwargs):
        raise AssertionError("missing_policy='merge' PySpark fit should fail before collect")

    def fail_to_pandas(self, *args, **kwargs):
        raise AssertionError("missing_policy='merge' PySpark fit should fail before toPandas")

    monkeypatch.setattr(SparkDataFrame, "collect", fail_collect)
    monkeypatch.setattr(SparkDataFrame, "toPandas", fail_to_pandas)

    with pytest.raises(NotImplementedError, match=SPARK_MERGE_FIT_MESSAGE):
        RiskBands(
            missing_policy="merge",
            missing_merge_criterion="nearest_event_rate",
        ).fit(sdf, y="target", column="score")


def test_merge_spark_transform_return_woe_still_fails(spark_session):
    binner, _ = fit_numeric_merge()
    sdf = _numeric_spark_frame(spark_session, [(None, 0), (1.0, 1)])

    with pytest.raises(NotImplementedError, match=SPARK_WOE_MESSAGE):
        binner.transform(sdf, column="score", return_woe=True)


def test_merge_no_fit_missing_spark_transform_uses_separate_bin_fallback(spark_session):
    fit_df = pd.DataFrame({"score": [-5.0, -4.0, 0.0, 3.0, 5.0] * 8, "target": [0, 0, 1, 1, 1] * 8})
    binner = RiskBands(
        max_bins=3,
        min_event_rate_diff=0.0,
        missing_policy="merge",
        missing_merge_criterion="nearest_event_rate",
        missing_merge_fallback="separate_bin",
    ).fit(fit_df, y="target", column="score")
    sdf = _numeric_spark_frame(spark_session, [(None, 0), (float("nan"), 1), (-5.0, 0)])

    observed = _only_column_values(binner.transform(sdf, column="score"), "score")

    assert binner.missing_merge_map_ == {}
    assert Counter(observed)["Missing"] == 2


def test_merge_no_fit_missing_spark_transform_raise_fallback_detects_missing(spark_session):
    fit_df = pd.DataFrame({"score": [-5.0, -4.0, 0.0, 3.0, 5.0] * 8, "target": [0, 0, 1, 1, 1] * 8})
    binner = RiskBands(
        max_bins=3,
        min_event_rate_diff=0.0,
        missing_policy="merge",
        missing_merge_criterion="nearest_event_rate",
        missing_merge_fallback="raise",
    ).fit(fit_df, y="target", column="score")
    sdf = _numeric_spark_frame(spark_session, [(None, 0), (-5.0, 0)])

    with pytest.raises(
        ValueError,
        match=(
            "missing_policy='merge' detected missing values during Spark transform for feature score, "
            "but no merge decision was learned during fit"
        ),
    ):
        binner.transform(sdf, column="score")


def test_merge_no_fit_missing_spark_transform_raise_fallback_allows_no_missing(spark_session):
    fit_df = pd.DataFrame({"score": [-5.0, -4.0, 0.0, 3.0, 5.0] * 8, "target": [0, 0, 1, 1, 1] * 8})
    binner = RiskBands(
        max_bins=3,
        min_event_rate_diff=0.0,
        missing_policy="merge",
        missing_merge_criterion="nearest_event_rate",
        missing_merge_fallback="raise",
    ).fit(fit_df, y="target", column="score")
    sdf = _numeric_spark_frame(spark_session, [(-5.0, 0), (0.0, 1)])

    transformed = binner.transform(sdf, column="score")

    assert transformed.__class__.__module__.startswith("pyspark")
    assert "Missing" not in _only_column_values(transformed, "score")


def test_categorical_no_fit_missing_spark_transform_uses_separate_bin_fallback(spark_session):
    fit_df = pd.DataFrame({"rating": ["A", "B", "C", "A", "B", "C"] * 8, "target": [0, 1, 1, 0, 1, 1] * 8})
    binner = RiskBands(
        max_bins=3,
        min_event_rate_diff=0.0,
        force_categorical=["rating"],
        missing_policy="merge",
        missing_merge_criterion="nearest_event_rate",
        missing_merge_fallback="separate_bin",
    ).fit(fit_df, y="target", column="rating")
    sdf = _categorical_spark_frame(spark_session, [(None, 0), ("Z", 1)])

    observed = _only_column_values(binner.transform(sdf, column="rating"), "rating")

    assert binner.missing_merge_map_ == {}
    assert Counter(observed)["Missing"] == 1


def test_categorical_no_fit_missing_spark_transform_raise_fallback_detects_null(spark_session):
    fit_df = pd.DataFrame({"rating": ["A", "B", "C", "A", "B", "C"] * 8, "target": [0, 1, 1, 0, 1, 1] * 8})
    binner = RiskBands(
        max_bins=3,
        min_event_rate_diff=0.0,
        force_categorical=["rating"],
        missing_policy="merge",
        missing_merge_criterion="nearest_event_rate",
        missing_merge_fallback="raise",
    ).fit(fit_df, y="target", column="rating")
    sdf = _categorical_spark_frame(spark_session, [(None, 0), ("A", 1)])

    with pytest.raises(
        ValueError,
        match=(
            "missing_policy='merge' detected missing values during Spark transform for feature rating, "
            "but no merge decision was learned during fit"
        ),
    ):
        binner.transform(sdf, column="rating")
