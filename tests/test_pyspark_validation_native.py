from importlib.util import find_spec
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from riskbands import RiskBands
from riskbands.reporting import load_bundle

pytestmark = pytest.mark.spark


@pytest.fixture(scope="session")
def spark_session():
    if find_spec("pyspark") is None:
        pytest.skip("PySpark is not installed")
    try:
        from pyspark.sql import SparkSession

        spark_local_dir = Path(".pytest_tmp/spark-local-native").resolve()
        spark_local_dir.mkdir(parents=True, exist_ok=True)
        spark = (
            SparkSession.builder.master("local[2]")
            .appName("riskbands-v210-native-validation")
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


def make_large_frame(n=6000):
    idx = np.arange(n)
    score = np.linspace(-5.0, 5.0, n)
    score_2 = np.sin(idx / 13.0)
    target = ((score >= 0) | ((idx % 17) == 0)).astype(int)
    return pd.DataFrame({"score": score, "score_2": score_2, "target": target})


def make_alignment_frame():
    values = np.array(
        [-10.0, -5.0, -2.0, -1.0, -0.1, 0.0, 0.1, 1.0, 2.0, 5.0, 10.0, np.nan] * 12,
        dtype=float,
    )
    score_2 = np.nan_to_num(values, nan=0.0) ** 2
    target = np.where(np.nan_to_num(values, nan=-1.0) >= 0.0, 1, 0)
    df = pd.DataFrame({"score": values, "score_2": score_2, "target": target})
    return df.sample(frac=1.0, random_state=7).reset_index(drop=True)


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


def comparable_profile(profile):
    comparable = profile.loc[:, ["variable", "bin_label", "n", "events", "event_rate"]].copy()
    comparable["bin_label"] = comparable["bin_label"].astype(str)
    comparable["n"] = pd.to_numeric(comparable["n"], errors="coerce").astype(int)
    comparable["events"] = pd.to_numeric(comparable["events"], errors="coerce").astype(float)
    comparable["event_rate"] = pd.to_numeric(comparable["event_rate"], errors="coerce").astype(float)
    return comparable.sort_values(["variable", "bin_label"]).reset_index(drop=True)


def test_spark_fit_and_transform_validate_do_not_collect_full_dataframes(spark_session, monkeypatch):
    df = make_large_frame()
    spark_df = spark_session.createDataFrame(df).repartition(3)
    calls = install_to_pandas_guard(monkeypatch, max_rows=2000)
    binner = RiskBands(strategy="supervised", max_bins=4, min_event_rate_diff=0.0, sample_size=400)

    binner.fit(spark_df, target="target", columns=["score", "score_2"], validate=True)
    transformed = binner.transform(spark_df, columns=["score", "score_2"], validate=True)

    assert transformed.__class__.__module__.startswith("pyspark")
    assert binner.source_profile_ is not None
    assert binner.application_profile_ is not None
    assert binner.fit_validation_report_["summary"]["n_rows_source"] == len(df)
    assert binner.transform_validation_report_["summary"]["n_application_rows"] == len(df)
    assert calls
    assert max(call["rows"] for call in calls) <= 2000


def test_spark_transform_validate_false_does_not_collect_profiles(spark_session, monkeypatch):
    df = make_large_frame(n=800)
    spark_df = spark_session.createDataFrame(df)
    binner = RiskBands(strategy="supervised", max_bins=4, min_event_rate_diff=0.0, sample_size=120)
    binner.fit(spark_df, target="target", columns=["score", "score_2"], validate=False)

    from pyspark.sql import DataFrame as SparkDataFrame

    def fail_to_pandas(self, *args, **kwargs):
        raise AssertionError("transform(validate=False) should not collect a Spark profile")

    monkeypatch.setattr(SparkDataFrame, "toPandas", fail_to_pandas)
    transformed = binner.transform(spark_df, columns=["score", "score_2"], validate=False)

    assert transformed.__class__.__module__.startswith("pyspark")


def test_spark_application_profile_matches_pandas_and_preserves_bin_target_alignment(spark_session):
    df = make_alignment_frame()
    binner = RiskBands(strategy="supervised", max_bins=4, min_event_rate_diff=0.0)
    binner.fit(df, y="target", columns=["score", "score_2"], validate=True)
    spark_df = spark_session.createDataFrame(df).repartition(4)

    spark_transformed = binner.transform(spark_df, columns=["score", "score_2"], validate=True)
    pandas_transformed = binner.transform(df[["score", "score_2"]])
    expected_profile = binner._build_profile_from_transformed(pandas_transformed, df["target"])

    assert spark_transformed.__class__.__module__.startswith("pyspark")
    assert_frame_equal(
        comparable_profile(binner.application_profile_),
        comparable_profile(expected_profile),
        check_dtype=False,
        atol=1e-12,
        rtol=1e-12,
    )
    assert binner.transform_validation_report_["summary"]["n_application_rows"] == len(df)


def test_spark_validation_temp_columns_are_collision_safe(spark_session):
    df = make_alignment_frame().rename(columns={"target": "__riskbands_bin_label"})
    df["__riskbands_target"] = "user-owned"
    binner = RiskBands(strategy="supervised", max_bins=4, min_event_rate_diff=0.0)
    binner.fit(df, y="__riskbands_bin_label", column="score", validate=True)
    spark_df = spark_session.createDataFrame(df).repartition(3)

    spark_transformed = binner.transform(spark_df, column="score", validate=True)

    assert spark_transformed.columns == ["score"]
    assert "__riskbands_bin_label" not in spark_transformed.columns
    assert "__riskbands_target" not in spark_transformed.columns
    assert binner.application_profile_ is not None
    assert int(binner.application_profile_["events"].sum()) == int(df["__riskbands_bin_label"].sum())
    assert binner.transform_validation_report_["summary"]["n_application_rows"] == len(df)
    assert [row["__riskbands_target"] for row in spark_df.select("__riskbands_target").distinct().collect()] == [
        "user-owned"
    ]


def test_spark_fit_then_pandas_transform_validate_preserves_fit_report(spark_session):
    df = make_alignment_frame()
    spark_df = spark_session.createDataFrame(df).repartition(3)
    binner = RiskBands(strategy="supervised", max_bins=4, min_event_rate_diff=0.0, sample_size=100)

    binner.fit(spark_df, target="target", columns=["score", "score_2"], validate=True)
    fit_report = binner.fit_validation_report_
    transformed = binner.transform(df[["score", "score_2", "target"]], validate=True)

    assert isinstance(transformed, pd.DataFrame)
    assert binner.fit_validation_report_ is fit_report
    assert binner.transform_validation_report_["backend"] == "pandas"
    assert binner.transform_validation_report_["summary"]["n_application_rows"] == len(df)


def test_spark_transform_validate_flags_controlled_event_rate_shift(spark_session):
    df = make_alignment_frame()
    binner = RiskBands(strategy="supervised", max_bins=4, min_event_rate_diff=0.0)
    binner.fit(df, y="target", columns=["score", "score_2"], validate=True)
    shifted = df.copy()
    row_number = np.arange(len(shifted))
    positive = shifted["score"].fillna(-1.0) >= 0.0
    shifted.loc[positive, "target"] = (row_number[positive] % 2 == 0).astype(int)
    spark_shifted = spark_session.createDataFrame(shifted).repartition(4)

    binner.transform(spark_shifted, columns=["score", "score_2"], validate=True)

    assert any(
        "possible_population_drift" in alert["alert_flags"]
        for alert in binner.transform_validation_report_["alerts"]
    )


def test_spark_fit_transform_roundtrip_bundle_preserves_reports(spark_session, tmp_path):
    df = make_alignment_frame()
    spark_df = spark_session.createDataFrame(df).repartition(3)
    binner = RiskBands(strategy="supervised", max_bins=4, min_event_rate_diff=0.0, sample_size=100)

    binner.fit(spark_df, target="target", columns=["score", "score_2"], validate=True)
    binner.transform(spark_df, columns=["score", "score_2"], validate=True)
    binner.export_bundle(tmp_path / "bundle")
    loaded = load_bundle(tmp_path / "bundle")

    assert loaded["fit_validation_report"] is not None
    assert loaded["transform_validation_report"] is not None
    assert loaded["reference_profile"] is not None
    assert loaded["reference_profile_source"] == "source_profile"
