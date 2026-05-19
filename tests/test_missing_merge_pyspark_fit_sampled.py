from collections import Counter

import numpy as np
import pandas as pd
import pytest

from riskbands import RiskBands
from riskbands.utils import dataframe_backend
from tests.test_fit_validate_true import ValidatingFakeSparkDataFrame
from tests.test_pyspark_fit_sampling import FakeSparkDataFrame, patch_fake_pyspark

pytestmark = pytest.mark.spark
pytest_plugins = ["tests.test_missing_values_pyspark_current_behavior"]


def _sampled_merge_frame(n=140):
    rows = []
    for idx in range(n):
        if idx % 4 == 0:
            score = np.nan
        else:
            score = float((idx % 9) - 4)
        target = int((score if pd.notna(score) else idx % 2) >= 0)
        if idx % 8 == 0:
            target = 1
        rows.append({"score": score, "target": target})
    return pd.DataFrame(rows)


def _assert_sampled_merge_metadata(binner, *, source_rows, sample_size):
    assert binner.input_backend_ == "pyspark"
    assert binner.fit_backend_ == "pandas_core"
    assert binner.backend_metadata_["input_backend"] == "pyspark"
    assert binner.backend_metadata_["fit_backend"] == "pandas_core"
    assert binner.backend_metadata_["fit_mode"] == "sampled_to_pandas"
    assert binner.sampling_metadata_["input_backend"] == "pyspark"
    assert binner.sampling_metadata_["fit_backend"] == "pandas_core"
    assert binner.sampling_metadata_["fit_mode"] == "sampled_to_pandas"
    assert binner.sampling_metadata_["sampling_applied"] is True
    assert binner.sampling_metadata_["n_rows_source"] == source_rows
    assert binner.sampling_metadata_["n_rows_fit"] <= sample_size
    assert binner.sampling_metadata_["sample_size_requested"] == sample_size
    assert binner.sampling_metadata_["merge_decision_learned_on_sample"] is True
    assert binner.sampling_metadata_["merge_decision_fit_mode"] == "sampled_to_pandas"
    assert binner.sampling_metadata_["merge_decision_n_rows_source"] == source_rows
    assert binner.sampling_metadata_["merge_decision_n_rows_fit"] == binner.sampling_metadata_["n_rows_fit"]
    assert binner.sampling_metadata_["merge_decision_sample_size_requested"] == sample_size
    assert "sampled-to-pandas" in binner.sampling_metadata_["sampling_caveat"]
    assert binner.metadata_["merge_decision_learned_on_sample"] is True
    assert binner.metadata_["sampling_caveat"] == binner.sampling_metadata_["sampling_caveat"]


@pytest.mark.parametrize("criterion", ["nearest_event_rate", "nearest_woe"])
def test_fit_spark_merge_uses_sampled_pandas_core_and_respects_sample_size(monkeypatch, criterion):
    patch_fake_pyspark(monkeypatch)
    pdf = _sampled_merge_frame()
    spark_df = FakeSparkDataFrame(pdf)
    sample_size = 50

    binner = RiskBands(
        max_bins=4,
        min_event_rate_diff=0.0,
        sample_size=sample_size,
        missing_policy="merge",
        missing_merge_criterion=criterion,
    ).fit(spark_df, y="target", column="score")

    _assert_sampled_merge_metadata(binner, source_rows=len(pdf), sample_size=sample_size)
    assert spark_df.ops["limits"] == [sample_size]
    assert spark_df.ops["to_pandas_columns"] == [["score", "target"]]
    assert binner.missing_merge_map_["score"]
    assert binner.missing_decision_log_["merge_decision_learned_on_sample"].eq(True).all()
    assert binner.missing_decision_log_["sampling_caveat"].eq(binner.sampling_metadata_["sampling_caveat"]).all()


def test_sampled_fit_fractional_sample_size_records_effective_fraction(monkeypatch):
    patch_fake_pyspark(monkeypatch)
    pdf = _sampled_merge_frame(n=120)
    spark_df = FakeSparkDataFrame(pdf)

    binner = RiskBands(
        max_bins=4,
        min_event_rate_diff=0.0,
        sample_size=0.5,
        missing_policy="merge",
        missing_merge_criterion="nearest_event_rate",
    ).fit(spark_df, y="target", column="score")

    assert binner.sampling_metadata_["sample_size_type"] == "fraction"
    assert binner.sampling_metadata_["sample_fraction_effective"] == 0.5
    assert binner.sampling_metadata_["merge_decision_sample_fraction_effective"] == 0.5
    assert binner.sampling_metadata_["n_rows_fit"] == 60


def test_sample_misses_missing_separate_bin_fallback_routes_spark_missing(spark_session, monkeypatch):
    pdf = pd.DataFrame(
        {
            "score": [-4.0, -3.0, -2.0, -1.0, 1.0, 2.0, None, np.nan],
            "target": [0, 0, 0, 0, 1, 1, 1, 0],
        }
    )
    monkeypatch.setattr(dataframe_backend, "_pyspark_dataframe_class", lambda: ValidatingFakeSparkDataFrame)
    fake_spark = ValidatingFakeSparkDataFrame(pdf, sample_mode="head")
    binner = RiskBands(
        max_bins=3,
        min_event_rate_diff=0.0,
        sample_size=0.75,
        missing_policy="merge",
        missing_merge_criterion="nearest_event_rate",
        missing_merge_fallback="separate_bin",
    ).fit(fake_spark, y="target", column="score")

    from pyspark.sql import DataFrame as SparkDataFrame
    from pyspark.sql import types as T

    monkeypatch.setattr(dataframe_backend, "_pyspark_dataframe_class", lambda: SparkDataFrame)
    schema = T.StructType(
        [
            T.StructField("score", T.DoubleType(), True),
            T.StructField("target", T.IntegerType(), True),
        ]
    )
    transform_sdf = spark_session.createDataFrame([(None, 1), (float("nan"), 0), (-4.0, 0)], schema=schema)

    observed = [row["score"] for row in binner.transform(transform_sdf, column="score").select("score").collect()]

    assert binner.missing_merge_map_ == {}
    assert binner.missing_decision_log_.iloc[0]["action"] == "no_missing_detected"
    assert Counter(observed)["Missing"] == 2


def test_sample_misses_missing_raise_fallback_fails_only_when_transform_has_missing(spark_session, monkeypatch):
    pdf = pd.DataFrame(
        {
            "score": [-4.0, -3.0, -2.0, -1.0, 1.0, 2.0, None, np.nan],
            "target": [0, 0, 0, 0, 1, 1, 1, 0],
        }
    )
    monkeypatch.setattr(dataframe_backend, "_pyspark_dataframe_class", lambda: ValidatingFakeSparkDataFrame)
    fake_spark = ValidatingFakeSparkDataFrame(pdf, sample_mode="head")
    binner = RiskBands(
        max_bins=3,
        min_event_rate_diff=0.0,
        sample_size=0.75,
        missing_policy="merge",
        missing_merge_criterion="nearest_event_rate",
        missing_merge_fallback="raise",
    ).fit(fake_spark, y="target", column="score")

    from pyspark.sql import DataFrame as SparkDataFrame
    from pyspark.sql import types as T

    monkeypatch.setattr(dataframe_backend, "_pyspark_dataframe_class", lambda: SparkDataFrame)
    schema = T.StructType(
        [
            T.StructField("score", T.DoubleType(), True),
            T.StructField("target", T.IntegerType(), True),
        ]
    )
    no_missing_sdf = spark_session.createDataFrame([(-4.0, 0), (1.0, 1)], schema=schema)
    missing_sdf = spark_session.createDataFrame([(None, 1), (-4.0, 0)], schema=schema)

    assert binner.transform(no_missing_sdf, column="score").__class__.__module__.startswith("pyspark")
    with pytest.raises(ValueError, match="no merge decision was learned during fit"):
        binner.transform(missing_sdf, column="score")
