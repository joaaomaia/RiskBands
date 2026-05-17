from collections import Counter

import pytest

from riskbands import RiskBands
from tests.test_missing_values_current_behavior import make_categorical_missing_frame, make_numeric_missing_frame
from tests.test_missing_values_pyspark_current_behavior import install_to_pandas_guard

pytestmark = pytest.mark.spark
pytest_plugins = ["tests.test_missing_values_pyspark_current_behavior"]


def test_separate_bin_pandas_fit_spark_categorical_null_is_missing(spark_session):
    binner = RiskBands(
        force_categorical=["grade"],
        missing_policy="separate_bin",
        min_event_rate_diff=0.0,
    ).fit(make_categorical_missing_frame(), y="target", column="grade")
    from pyspark.sql import types as T

    schema = T.StructType(
        [
            T.StructField("grade", T.StringType(), True),
            T.StructField("target", T.IntegerType(), True),
        ]
    )
    sdf = spark_session.createDataFrame([(None, 1), ("A", 0), ("Z", 1)], schema=schema)

    transformed = binner.transform(sdf, column="grade")
    observed = transformed.toPandas()["grade"].tolist()

    assert transformed.__class__.__module__.startswith("pyspark")
    assert Counter(observed)["Missing"] == 1


def test_separate_bin_pandas_fit_spark_numeric_null_and_nan_are_missing(spark_session):
    binner = RiskBands(missing_policy="separate_bin", min_event_rate_diff=0.0).fit(
        make_numeric_missing_frame(),
        y="target",
        column="score",
    )
    from pyspark.sql import types as T

    schema = T.StructType(
        [
            T.StructField("score", T.DoubleType(), True),
            T.StructField("target", T.IntegerType(), True),
        ]
    )
    sdf = spark_session.createDataFrame([(None, 0), (float("nan"), 1), (1.0, 0)], schema=schema)

    observed = binner.transform(sdf, column="score").toPandas()["score"].tolist()

    assert Counter(observed)["Missing"] == 2


def test_separate_bin_spark_fit_and_validate_keeps_aggregate_collection_guard(spark_session, monkeypatch):
    from pyspark.sql import types as T

    rows = [(None if idx % 7 == 0 else ("A" if idx % 2 == 0 else "B"), int(idx % 3 == 0)) for idx in range(80)]
    schema = T.StructType(
        [
            T.StructField("grade", T.StringType(), True),
            T.StructField("target", T.IntegerType(), True),
        ]
    )
    sdf = spark_session.createDataFrame(rows, schema=schema).repartition(2)

    binner = RiskBands(
        force_categorical=["grade"],
        missing_policy="separate_bin",
        min_event_rate_diff=0.0,
        sample_size=80,
    ).fit(sdf, y="target", column="grade", validate=True)
    calls = install_to_pandas_guard(monkeypatch, max_rows=30)

    transformed = binner.transform(sdf, column="grade", validate=True)
    missing_rows = binner.application_profile_.loc[binner.application_profile_["is_missing_bin"]]

    assert transformed.__class__.__module__.startswith("pyspark")
    assert calls
    assert max(call["rows"] for call in calls) <= 30
    assert len(missing_rows) == 1
    assert missing_rows.iloc[0]["bin_label"] == "Missing"
    assert binner.transform_validation_report_["backend"] == "pyspark"
