import numpy as np
import pandas as pd
import pytest

from riskbands import RiskBands

pytest_plugins = ["tests.test_missing_values_pyspark_current_behavior"]


def test_forbid_pandas_numeric_missing_fit_raises():
    df = pd.DataFrame({"score": [1.0, np.nan, 3.0], "target": [0, 1, 0]})

    with pytest.raises(ValueError, match="missing_policy='forbid'.*fit.*score=1"):
        RiskBands(missing_policy="forbid").fit(df, y="target", column="score")


def test_forbid_pandas_categorical_missing_fit_raises():
    df = pd.DataFrame({"grade": ["A", None, "B"], "target": [0, 1, 0]})

    with pytest.raises(ValueError, match="missing_policy='forbid'.*grade=1"):
        RiskBands(missing_policy="forbid", force_categorical=["grade"]).fit(
            df,
            y="target",
            column="grade",
        )


def test_forbid_pandas_transform_missing_raises():
    df = pd.DataFrame({"score": [1.0, 2.0, 3.0, 4.0] * 8, "target": [0, 0, 1, 1] * 8})
    binner = RiskBands(missing_policy="forbid", max_bins=2, min_event_rate_diff=0.0).fit(
        df,
        y="target",
        column="score",
    )

    with pytest.raises(ValueError, match="missing_policy='forbid'.*transform.*score=1"):
        binner.transform(pd.DataFrame({"score": [1.0, np.nan]}))


def test_forbid_without_missing_fits_and_transforms():
    df = pd.DataFrame({"score": [1.0, 2.0, 3.0, 4.0] * 8, "target": [0, 0, 1, 1] * 8})
    binner = RiskBands(missing_policy="forbid", max_bins=2, min_event_rate_diff=0.0).fit(
        df,
        y="target",
        column="score",
    )

    transformed = binner.transform(df[["score"]])

    assert transformed.shape == (len(df), 1)
    assert binner.missing_policy_ == "forbid"


def test_standard_does_not_raise_on_missing():
    df = pd.DataFrame({"score": [1.0, np.nan, 3.0, 4.0] * 8, "target": [0, 1, 0, 1] * 8})

    binner = RiskBands(missing_policy="standard", max_bins=2, min_event_rate_diff=0.0).fit(
        df,
        y="target",
        column="score",
    )

    assert "Missing" in set(binner.transform(df[["score"]])["score"])


@pytest.mark.spark
def test_forbid_spark_numeric_null_and_nan_fit_raises(spark_session):
    from pyspark.sql import types as T

    schema = T.StructType(
        [
            T.StructField("score", T.DoubleType(), True),
            T.StructField("target", T.IntegerType(), True),
        ]
    )
    sdf = spark_session.createDataFrame([(1.0, 0), (None, 1), (float("nan"), 0)], schema=schema)

    with pytest.raises(ValueError, match="pyspark.*score=2"):
        RiskBands(missing_policy="forbid").fit(sdf, y="target", column="score")


@pytest.mark.spark
def test_forbid_spark_categorical_null_fit_raises(spark_session):
    from pyspark.sql import types as T

    schema = T.StructType(
        [
            T.StructField("grade", T.StringType(), True),
            T.StructField("target", T.IntegerType(), True),
        ]
    )
    sdf = spark_session.createDataFrame([("A", 0), (None, 1), ("B", 0)], schema=schema)

    with pytest.raises(ValueError, match="pyspark.*grade=1"):
        RiskBands(missing_policy="forbid", force_categorical=["grade"]).fit(
            sdf,
            y="target",
            column="grade",
        )


@pytest.mark.spark
def test_forbid_pandas_fit_spark_numeric_null_and_nan_transform_raises(spark_session):
    from pyspark.sql import types as T

    df = pd.DataFrame({"score": [1.0, 2.0, 3.0, 4.0] * 8, "target": [0, 0, 1, 1] * 8})
    binner = RiskBands(missing_policy="forbid", max_bins=2, min_event_rate_diff=0.0).fit(
        df,
        y="target",
        column="score",
    )

    schema = T.StructType([T.StructField("score", T.DoubleType(), True)])
    sdf = spark_session.createDataFrame([(1.0,), (None,), (float("nan"),)], schema=schema)

    with pytest.raises(ValueError, match="missing_policy='forbid'.*transform.*pyspark.*score=2"):
        binner.transform(sdf, column="score")
