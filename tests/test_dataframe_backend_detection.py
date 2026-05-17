from importlib.util import find_spec

import pandas as pd
import pytest

import riskbands
from riskbands.utils import dataframe_backend
from riskbands.utils.dataframe_backend import detect_dataframe_backend


def test_pandas_dataframe_and_series_are_detected_as_pandas():
    df = pd.DataFrame({"x": [1, 2, 3]})

    assert detect_dataframe_backend(df) == "pandas"
    assert detect_dataframe_backend(df["x"]) == "pandas"


def test_unknown_dataframe_backend_raises_clear_type_error():
    with pytest.raises(TypeError, match="pandas DataFrame/Series or a PySpark DataFrame"):
        detect_dataframe_backend(object(), argument_name="data")


def test_fake_pyspark_dataframe_type_can_be_detected_without_public_api(monkeypatch):
    class FakeSparkDataFrame:
        pass

    monkeypatch.setattr(dataframe_backend, "_pyspark_dataframe_class", lambda: FakeSparkDataFrame)

    assert detect_dataframe_backend(FakeSparkDataFrame()) == "pyspark"


@pytest.mark.skipif(find_spec("pyspark") is None, reason="PySpark is optional and not installed")
def test_real_pyspark_dataframe_is_detected_when_available():
    from pyspark.sql import SparkSession

    spark = SparkSession.builder.master("local[1]").appName("riskbands-backend-detection").getOrCreate()
    try:
        spark_df = spark.createDataFrame([(1,), (2,)], ["x"])
        assert detect_dataframe_backend(spark_df) == "pyspark"
    finally:
        spark.stop()


def test_import_does_not_expose_public_spark_specific_names():
    prohibited = {
        "SparkRiskBands",
        "RiskBandsSpark",
        "SparkBinner",
        "fit_spark",
        "transform_spark",
    }

    assert prohibited.isdisjoint(set(riskbands.__all__))
    assert not any(hasattr(riskbands, name) for name in prohibited)
