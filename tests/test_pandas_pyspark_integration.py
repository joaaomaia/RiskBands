from importlib.util import find_spec
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from riskbands import RiskBands
from riskbands.reporting import load_bundle


def make_integration_frame(n=260, seed=151):
    rng = np.random.default_rng(seed)
    score = np.linspace(-4, 4, n)
    low_card = np.where(score < -1, "low", np.where(score > 1, "high", "mid"))
    proba = 1 / (1 + np.exp(-1.7 * score))
    target = (rng.random(n) < proba).astype(int)
    month = rng.choice([202401, 202402, 202403, 202404], size=n)
    df = pd.DataFrame(
        {
            "score": score,
            "low_card": low_card,
            "month": month,
            "target": target,
        }
    )
    df.loc[[5, 37], "score"] = np.nan
    return df


def make_edge_frame(binner):
    splits = list(binner._per_feature_binners["score"].models_["score"].splits)
    values = [-1e9, splits[0], (splits[0] + splits[-1]) / 2, splits[-1], 1e9, np.nan]
    return pd.DataFrame(
        {
            "score": values,
            "target": [0, 0, 1, 1, 1, 0],
            "month": [202405] * len(values),
        }
    )


def fit_pandas_binner(**kwargs):
    df = make_integration_frame()
    max_bins = kwargs.pop("max_bins", 4)
    binner = RiskBands(strategy="supervised", max_bins=max_bins, min_event_rate_diff=0.0, **kwargs)
    binner.fit(df, y="target", column="score", time_col="month")
    return binner, df


def test_integration_fit_pandas_transform_pandas_with_validation_and_bundle(tmp_path):
    binner, df = fit_pandas_binner(min_n_bins=3)
    app = make_edge_frame(binner)

    transformed = binner.transform(app[["score", "target"]], validate=True)
    binner.export_bundle(tmp_path / "bundle")
    loaded = load_bundle(tmp_path / "bundle")

    assert isinstance(transformed, pd.DataFrame)
    assert binner.validation_report_["validation_type"] == "transform"
    assert binner.min_n_bins_metadata_["min_n_bins"] == 3
    assert loaded["reference_profile"] is not None
    assert loaded["bundle_schema_version"] == "2.1"


def test_integration_min_n_bins_infeasible_is_soft_warning():
    binner, _ = fit_pandas_binner(min_n_bins=5, max_bins=2)

    assert binner.min_n_bins_metadata_["min_n_bins_reached"] is False
    assert binner.min_n_bins_metadata_["n_regular_bins"] <= 2


@pytest.fixture(scope="session")
def spark_session():
    if find_spec("pyspark") is None:
        pytest.skip("PySpark is not installed")
    try:
        from pyspark.sql import SparkSession

        spark_local_dir = Path(".pytest_tmp/spark-local-integration").resolve()
        spark_local_dir.mkdir(parents=True, exist_ok=True)
        spark = (
            SparkSession.builder.master("local[2]")
            .appName("riskbands-integration")
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


pytestmark_spark = pytest.mark.spark


@pytestmark_spark
def test_integration_fit_pandas_transform_spark_matches_pandas(spark_session):
    binner, _ = fit_pandas_binner()
    app = make_edge_frame(binner)
    spark_df = spark_session.createDataFrame(app)

    pandas_out = binner.transform(app[["score"]]).reset_index(drop=True)
    spark_out = binner.transform(spark_df, column="score").toPandas().reset_index(drop=True)

    assert_frame_equal(spark_out, pandas_out)


@pytestmark_spark
def test_integration_fit_spark_transform_spark_and_pandas(spark_session):
    df = make_integration_frame()
    spark_df = spark_session.createDataFrame(df)
    binner = RiskBands(strategy="supervised", max_bins=4, min_event_rate_diff=0.0, sample_size=80)

    binner.fit(spark_df, target="target", column="score", time_col="month")
    spark_out = binner.transform(spark_df, column="score")
    pandas_out = binner.transform(df[["score"]])

    assert spark_out.__class__.__module__.startswith("pyspark")
    assert list(pandas_out.columns) == ["score"]
    assert not binner.binning_table().empty


@pytestmark_spark
def test_integration_fit_validate_true_spark_and_transform_validate_true_spark(spark_session):
    df = make_integration_frame(n=140)
    spark_df = spark_session.createDataFrame(df)
    binner = RiskBands(strategy="supervised", max_bins=3, min_event_rate_diff=0.0, sample_size=0.5)

    binner.fit(spark_df, target="target", column="score", validate=True)
    transformed = binner.transform(spark_df, column="score", validate=True)

    assert transformed.__class__.__module__.startswith("pyspark")
    assert binner.fit_profile_ is not None
    assert binner.application_profile_ is not None
    assert binner.fit_validation_report_ is not None
    assert binner.transform_validation_report_ is not None
    assert binner.sampling_metadata_["sample_size_type"] == "fraction"


@pytestmark_spark
def test_integration_sample_size_absolute_and_fractional_spark(spark_session):
    df = make_integration_frame(n=120)
    spark_df = spark_session.createDataFrame(df)
    absolute = RiskBands(strategy="supervised", max_bins=3, min_event_rate_diff=0.0, sample_size=30)
    fractional = RiskBands(strategy="supervised", max_bins=3, min_event_rate_diff=0.0, sample_size=0.25)

    absolute.fit(spark_df, target="target", column="score")
    fractional.fit(spark_df, target="target", column="score")

    assert absolute.sampling_metadata_["n_rows_fit"] <= 30
    assert fractional.sampling_metadata_["sample_size_type"] == "fraction"
