from importlib.util import find_spec
from pathlib import Path

import pytest

from tests.test_missing_values_current_behavior import (
    fit_categorical_missing_binner,
    fit_numeric_missing_binner,
)

pytestmark = pytest.mark.spark


@pytest.fixture(scope="session")
def spark_session():
    if find_spec("pyspark") is None:
        pytest.skip("PySpark is not installed")
    try:
        from pyspark.sql import SparkSession

        spark_local_dir = Path(".pytest_tmp/spark-local-missing-current").resolve()
        spark_local_dir.mkdir(parents=True, exist_ok=True)
        spark = (
            SparkSession.builder.master("local[2]")
            .appName("riskbands-missing-current")
            .config("spark.ui.enabled", "false")
            .config("spark.sql.shuffle.partitions", "2")
            .config("spark.driver.memory", "1g")
            .config("spark.local.dir", str(spark_local_dir))
            .getOrCreate()
        )
    except Exception as exc:
        pytest.skip(f"PySpark runtime is not available: {exc}")
    yield spark
    spark.stop()


def install_to_pandas_guard(monkeypatch, *, max_rows):
    from pyspark.sql import DataFrame as SparkDataFrame

    original = SparkDataFrame.toPandas
    calls = []

    def guarded_to_pandas(self, *args, **kwargs):
        row_count = int(self.limit(max_rows + 1).count())
        calls.append({"rows": row_count, "columns": list(self.columns)})
        if row_count > max_rows:
            raise AssertionError(
                f"Unexpected full Spark DataFrame toPandas with {row_count} rows and columns {self.columns}"
            )
        return original(self, *args, **kwargs)

    monkeypatch.setattr(SparkDataFrame, "toPandas", guarded_to_pandas)
    return calls


def test_spark_numeric_null_and_nan_transform_to_missing_label(spark_session):
    binner, _ = fit_numeric_missing_binner()
    from pyspark.sql import types as T

    schema = T.StructType(
        [
            T.StructField("score", T.DoubleType(), True),
            T.StructField("target", T.IntegerType(), True),
        ]
    )
    spark_df = spark_session.createDataFrame(
        [(None, 0), (float("nan"), 1), (-5.0, 0), (4.0, 1)],
        schema=schema,
    )

    transformed = binner.transform(spark_df, column="score")
    observed = transformed.toPandas()["score"].tolist()

    assert transformed.__class__.__module__.startswith("pyspark")
    assert observed[0] == "Missing"
    assert observed[1] == "Missing"
    assert observed[2] != "Missing"
    assert observed[3] != "Missing"


def test_spark_categorical_null_follows_current_missing_token_mapping(spark_session):
    binner, _ = fit_categorical_missing_binner()
    mapping = binner.get_bin_mapping("grade")
    mapping_by_category = dict(zip(mapping["categoria"].astype(str), mapping["bin"], strict=False))
    from pyspark.sql import types as T

    schema = T.StructType(
        [
            T.StructField("grade", T.StringType(), True),
            T.StructField("target", T.IntegerType(), True),
        ]
    )
    spark_df = spark_session.createDataFrame(
        [(None, 1), ("Z", 0), ("B", 1)],
        schema=schema,
    )

    transformed = binner.transform(spark_df, column="grade")
    observed = transformed.toPandas()["grade"].tolist()

    assert transformed.__class__.__module__.startswith("pyspark")
    assert observed[0] == mapping_by_category["_MISSING_"]
    assert observed[1] == mapping_by_category["_UNKNOWN_"]
    assert str(observed[0]).lower() != "missing"


def test_spark_transform_validate_builds_missing_profile_from_aggregates(spark_session, monkeypatch):
    binner, _ = fit_numeric_missing_binner(validate=True)
    from pyspark.sql import types as T

    rows = []
    for idx in range(120):
        if idx % 15 == 0:
            value = None
        elif idx % 15 == 1:
            value = float("nan")
        else:
            value = float((idx % 10) - 5)
        target = int(idx % 3 == 0)
        rows.append((value, target))

    schema = T.StructType(
        [
            T.StructField("score", T.DoubleType(), True),
            T.StructField("target", T.IntegerType(), True),
        ]
    )
    spark_df = spark_session.createDataFrame(rows, schema=schema).repartition(2)
    calls = install_to_pandas_guard(monkeypatch, max_rows=30)

    transformed = binner.transform(spark_df, column="score", validate=True)
    missing_rows = binner.application_profile_.loc[binner.application_profile_["is_missing_bin"]]

    assert transformed.__class__.__module__.startswith("pyspark")
    assert calls
    assert max(call["rows"] for call in calls) <= 30
    assert len(missing_rows) == 1
    assert missing_rows.iloc[0]["bin_label"] == "Missing"
    assert int(missing_rows.iloc[0]["n"]) == 16
    assert binner.transform_validation_report_["backend"] == "pyspark"
    assert binner.transform_validation_report_["summary"]["n_application_rows"] == 120
