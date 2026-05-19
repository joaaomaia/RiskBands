import math

import pytest

from riskbands import RiskBands

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


def _categorical_spark_frame(spark_session, rows):
    from pyspark.sql import types as T

    schema = T.StructType(
        [
            T.StructField("rating", T.StringType(), True),
            T.StructField("target", T.IntegerType(), True),
        ]
    )
    return spark_session.createDataFrame(rows, schema=schema)


def _mixed_spark_frame(spark_session, rows):
    from pyspark.sql import types as T

    schema = T.StructType(
        [
            T.StructField("score", T.DoubleType(), True),
            T.StructField("rating", T.StringType(), True),
            T.StructField("target", T.IntegerType(), True),
        ]
    )
    return spark_session.createDataFrame(rows, schema=schema)


def _values(spark_df, column):
    return [row[column] for row in spark_df.select(column).collect()]


def _numeric_fit_rows():
    rows = []
    for _ in range(5):
        rows.extend(
            [
                (-5.0, 0),
                (-4.0, 0),
                (-2.0, 0),
                (0.0, 1),
                (2.0, 1),
                (4.0, 1),
                (None, 0),
                (float("nan"), 1),
            ]
        )
    return rows


def _categorical_fit_rows():
    rows = []
    for _ in range(6):
        rows.extend(
            [
                ("A", 0),
                ("A", 0),
                ("B", 0),
                ("B", 1),
                ("C", 1),
                ("C", 1),
                (None, 0),
                (None, 1),
            ]
        )
    return rows


@pytest.mark.parametrize("criterion", ["nearest_event_rate", "nearest_woe"])
def test_numeric_fit_spark_transform_same_and_new_spark_df(spark_session, criterion):
    fit_rows = _numeric_fit_rows()
    fit_sdf = _numeric_spark_frame(spark_session, fit_rows)
    binner = RiskBands(
        max_bins=3,
        min_event_rate_diff=0.0,
        sample_size=len(fit_rows),
        missing_policy="merge",
        missing_merge_criterion=criterion,
    ).fit(fit_sdf, y="target", column="score")
    learned_label = binner.missing_merge_map_["score"]

    same_output = binner.transform(fit_sdf, column="score")
    new_sdf = _numeric_spark_frame(spark_session, [(None, 1), (float("nan"), 0), (-5.0, 0), (4.0, 1)])
    new_output = binner.transform(new_sdf, column="score")
    observed = _values(new_output, "score")

    assert same_output.__class__.__module__.startswith("pyspark")
    assert new_output.__class__.__module__.startswith("pyspark")
    assert observed.count(learned_label) >= 2
    assert "Missing" not in observed
    assert not any(isinstance(value, float) and math.isnan(value) for value in observed)


@pytest.mark.parametrize("criterion", ["nearest_event_rate", "nearest_woe"])
def test_categorical_fit_spark_transform_routes_null_and_keeps_unknown_distinct(spark_session, criterion):
    fit_rows = _categorical_fit_rows()
    fit_sdf = _categorical_spark_frame(spark_session, fit_rows)
    binner = RiskBands(
        max_bins=3,
        min_event_rate_diff=0.0,
        force_categorical=["rating"],
        sample_size=len(fit_rows),
        missing_policy="merge",
        missing_merge_criterion=criterion,
    ).fit(fit_sdf, y="target", column="rating")
    learned_label = str(binner.missing_merge_map_["rating"])

    output = binner.transform(
        _categorical_spark_frame(spark_session, [(None, 1), ("Z", 0), ("A", 0)]),
        column="rating",
    )
    observed = [str(value) for value in _values(output, "rating")]

    assert output.__class__.__module__.startswith("pyspark")
    assert observed[0] == learned_label
    assert observed[1] != learned_label
    assert observed[1] != "Missing"


def test_fit_spark_transform_spark_multiple_features(spark_session):
    rows = []
    for _ in range(5):
        rows.extend(
            [
                (-5.0, "A", 0),
                (-3.0, "A", 0),
                (0.0, "B", 1),
                (3.0, "C", 1),
                (None, None, 1),
                (float("nan"), None, 0),
            ]
        )
    fit_sdf = _mixed_spark_frame(spark_session, rows)
    binner = RiskBands(
        max_bins=3,
        min_event_rate_diff=0.0,
        force_categorical=["rating"],
        sample_size=len(rows),
        missing_policy="merge",
        missing_merge_criterion="nearest_event_rate",
    ).fit(fit_sdf, y="target", columns=["score", "rating"])

    output = binner.transform(
        _mixed_spark_frame(spark_session, [(None, None, 1), (float("nan"), "C", 0), (-5.0, "A", 0)]),
        columns=["score", "rating"],
    )
    score_values = [str(value) for value in _values(output, "score")]
    rating_values = [str(value) for value in _values(output, "rating")]

    assert output.__class__.__module__.startswith("pyspark")
    assert score_values[0] == str(binner.missing_merge_map_["score"])
    assert score_values[1] == str(binner.missing_merge_map_["score"])
    assert rating_values[0] == str(binner.missing_merge_map_["rating"])
    assert "Missing" not in rating_values
