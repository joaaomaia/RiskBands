from collections import Counter

import pandas as pd
import pytest

from riskbands import RiskBands
from tests.test_missing_merge_nearest_event_rate_pandas import (
    fit_numeric_merge,
    make_categorical_event_rate_frame,
)

pytestmark = pytest.mark.spark
pytest_plugins = ["tests.test_missing_values_pyspark_current_behavior"]


def _numeric_spark_frame(spark_session, rows):
    from pyspark.sql import types as T

    schema = T.StructType([T.StructField("score", T.DoubleType(), True)])
    return spark_session.createDataFrame([(value,) for value in rows], schema=schema)


def _categorical_spark_frame(spark_session, rows):
    from pyspark.sql import types as T

    schema = T.StructType([T.StructField("rating", T.StringType(), True)])
    return spark_session.createDataFrame([(value,) for value in rows], schema=schema)


def _mixed_spark_frame(spark_session, rows):
    from pyspark.sql import types as T

    schema = T.StructType(
        [
            T.StructField("score", T.DoubleType(), True),
            T.StructField("rating", T.StringType(), True),
        ]
    )
    return spark_session.createDataFrame(rows, schema=schema)


def _values(spark_df, column):
    return [row[column] for row in spark_df.select(column).collect()]


def _string_counts(values):
    return Counter(str(value) for value in values)


def _fit_categorical_merge():
    return RiskBands(
        max_bins=3,
        min_event_rate_diff=0.0,
        force_categorical=["rating"],
        missing_policy="merge",
        missing_merge_criterion="nearest_event_rate",
    ).fit(make_categorical_event_rate_frame(), y="target", column="rating")


def _fit_no_decision_mixed_binner(*, fallback):
    fit_df = pd.DataFrame(
        {
            "score": [-5.0, -4.0, 0.0, 3.0, 5.0] * 8,
            "rating": ["A", "A", "B", "C", "C"] * 8,
            "target": [0, 0, 1, 1, 1] * 8,
        }
    )
    return RiskBands(
        max_bins=3,
        min_event_rate_diff=0.0,
        force_categorical=["rating"],
        missing_policy="merge",
        missing_merge_criterion="nearest_event_rate",
        missing_merge_fallback=fallback,
    ).fit(fit_df, y="target", columns=["score", "rating"])


def test_numeric_null_routes_to_learned_missing_merge_label(spark_session):
    binner, _ = fit_numeric_merge()

    observed = _values(binner.transform(_numeric_spark_frame(spark_session, [None]), column="score"), "score")

    assert [str(value) for value in observed] == [str(binner.missing_merge_map_["score"])]


def test_numeric_nan_routes_to_learned_missing_merge_label(spark_session):
    binner, _ = fit_numeric_merge()

    observed = _values(
        binner.transform(_numeric_spark_frame(spark_session, [float("nan")]), column="score"),
        "score",
    )

    assert [str(value) for value in observed] == [str(binner.missing_merge_map_["score"])]


def test_numeric_null_and_nan_in_same_spark_frame_route_to_merge_label(spark_session):
    binner, _ = fit_numeric_merge()

    observed = _values(
        binner.transform(_numeric_spark_frame(spark_session, [None, float("nan"), -5.0]), column="score"),
        "score",
    )

    assert _string_counts(observed)[str(binner.missing_merge_map_["score"])] >= 2
    assert "Missing" not in _string_counts(observed)


def test_categorical_null_routes_to_merge_label_and_unknown_stays_distinct(spark_session):
    binner = _fit_categorical_merge()
    expected_unknown = binner.transform(pd.DataFrame({"rating": ["Z"]}), column="rating").loc[0, "rating"]

    transformed = binner.transform(_categorical_spark_frame(spark_session, [None, "Z", "A"]), column="rating")
    observed = _values(transformed, "rating")

    assert str(observed[0]) == str(binner.missing_merge_map_["rating"])
    assert str(observed[1]) == str(expected_unknown)
    assert str(observed[1]) != str(observed[0])
    assert str(observed[1]) != "Missing"


def test_separate_bin_fallback_without_decision_handles_numeric_and_categorical_missing(
    spark_session,
):
    binner = _fit_no_decision_mixed_binner(fallback="separate_bin")
    assert binner.missing_merge_map_ == {}
    spark_df = _mixed_spark_frame(
        spark_session,
        [(None, None), (float("nan"), "Z"), (-5.0, "A")],
    )

    transformed = binner.transform(spark_df, columns=["score", "rating"])

    assert _string_counts(_values(transformed, "score"))["Missing"] == 2
    assert _string_counts(_values(transformed, "rating"))["Missing"] == 1


def test_raise_fallback_without_decision_reports_one_missing_column(spark_session):
    binner = _fit_no_decision_mixed_binner(fallback="raise")
    spark_df = _mixed_spark_frame(
        spark_session,
        [(None, None), (float("nan"), "Z"), (-5.0, "A")],
    )

    with pytest.raises(
        ValueError,
        match="missing_policy='merge' detected missing values during Spark transform for feature (score|rating)",
    ):
        binner.transform(spark_df, columns=["score", "rating"])

    assert binner.missing_transform_fallback_log_ is not None
    assert binner.missing_transform_fallback_log_.iloc[0]["variable"] in {"score", "rating"}


def test_raise_fallback_without_decision_allows_transform_when_no_missing(spark_session):
    binner = _fit_no_decision_mixed_binner(fallback="raise")
    spark_df = _mixed_spark_frame(spark_session, [(-5.0, "A"), (0.0, "B"), (5.0, "Z")])

    transformed = binner.transform(spark_df, columns=["score", "rating"])

    assert transformed.__class__.__module__.startswith("pyspark")
    assert "Missing" not in _string_counts(_values(transformed, "score"))
    assert "Missing" not in _string_counts(_values(transformed, "rating"))
