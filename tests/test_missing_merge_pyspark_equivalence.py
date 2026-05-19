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


def _canonical(value):
    if pd.isna(value):
        return "<NA>"
    return str(value)


def _counter(values):
    return Counter(_canonical(value) for value in values)


def _spark_values(spark_df, column):
    return [row[column] for row in spark_df.select(column).collect()]


def _numeric_spark_frame(spark_session, rows):
    from pyspark.sql import types as T

    schema = T.StructType([T.StructField("score", T.DoubleType(), True)])
    return spark_session.createDataFrame([(value,) for value in rows], schema=schema)


def _categorical_spark_frame(spark_session, rows):
    from pyspark.sql import types as T

    schema = T.StructType([T.StructField("rating", T.StringType(), True)])
    return spark_session.createDataFrame([(value,) for value in rows], schema=schema)


def _assert_transform_equivalent(binner, pandas_df, spark_df, column):
    pandas_values = binner.transform(pandas_df, column=column)[column].tolist()
    spark_values = _spark_values(binner.transform(spark_df, column=column), column)

    assert _counter(spark_values) == _counter(pandas_values)


@pytest.mark.parametrize(
    "fit_factory",
    [
        fit_numeric_merge,
        fit_numeric_woe_merge,
    ],
)
def test_numeric_supervised_pandas_fit_spark_transform_matches_pandas(
    spark_session,
    fit_factory,
):
    binner, fit_df = fit_factory()
    assert fit_df["score"].isna().any()
    assert binner.missing_merge_map_["score"]

    transform_values = [None, float("nan"), -5.0, -3.0, 0.0, 3.0, 5.0, 8.0]
    pandas_df = pd.DataFrame({"score": transform_values})
    spark_df = _numeric_spark_frame(spark_session, transform_values)

    _assert_transform_equivalent(binner, pandas_df, spark_df, "score")


def test_categorical_nearest_event_rate_pandas_fit_spark_transform_matches_pandas(spark_session):
    fit_df = make_categorical_event_rate_frame()
    binner = RiskBands(
        max_bins=3,
        min_event_rate_diff=0.0,
        force_categorical=["rating"],
        missing_policy="merge",
        missing_merge_criterion="nearest_event_rate",
    ).fit(fit_df, y="target", column="rating")
    assert fit_df["rating"].isna().any()
    assert binner.missing_merge_map_["rating"]

    transform_values = [None, "A", "B", "C", "Z", "A", None]
    pandas_df = pd.DataFrame({"rating": transform_values})
    spark_df = _categorical_spark_frame(spark_session, transform_values)

    _assert_transform_equivalent(binner, pandas_df, spark_df, "rating")


def test_categorical_nearest_woe_pandas_fit_spark_transform_matches_pandas(spark_session):
    binner, fit_df = fit_categorical_woe_merge()
    assert fit_df["rating"].isna().any()
    assert binner.missing_merge_map_["rating"]

    transform_values = [None, "A", "B", "C", "Z", "A", None]
    pandas_df = pd.DataFrame({"rating": transform_values})
    spark_df = _categorical_spark_frame(spark_session, transform_values)

    _assert_transform_equivalent(binner, pandas_df, spark_df, "rating")


def test_numeric_unsupervised_missing_merge_equivalence_not_supported_by_pandas_transform():
    fit_df = pd.DataFrame({"score": [-5.0, -4.0, 0.0, 3.0, 5.0] * 8, "target": [0, 0, 1, 1, 1] * 8})
    binner = RiskBands(
        strategy="unsupervised",
        max_bins=3,
        missing_policy="merge",
        missing_merge_criterion="nearest_event_rate",
        missing_merge_fallback="separate_bin",
    ).fit(fit_df, y="target", column="score")

    with pytest.raises(ValueError, match="KBinsDiscretizer does not accept missing values"):
        binner.transform(pd.DataFrame({"score": [float("nan"), -5.0]}), column="score")
