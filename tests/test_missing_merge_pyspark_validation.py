from collections import Counter

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from riskbands import RiskBands
from tests.test_missing_merge_nearest_event_rate_pandas import fit_numeric_merge
from tests.test_missing_values_pyspark_current_behavior import install_to_pandas_guard

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


def _bin_counts(profile):
    return Counter(profile["bin_label"].astype(str).tolist())


def test_merge_spark_transform_validate_true_profiles_final_merged_bin(spark_session, monkeypatch):
    binner, _ = fit_numeric_merge()
    learned_label = binner.missing_merge_map_["score"]
    reference_before = binner.reference_profile_.copy()
    sdf = _numeric_spark_frame(
        spark_session,
        [(None, 1), (float("nan"), 0), (-5.0, 0), (-3.0, 0), (0.0, 1), (3.0, 1), (5.0, 1)],
    ).repartition(2)
    calls = install_to_pandas_guard(monkeypatch, max_rows=20)

    transformed = binner.transform(sdf, column="score", validate=True)
    profile = binner.application_profile_

    assert transformed.__class__.__module__.startswith("pyspark")
    assert profile is not None
    assert binner.transform_validation_report_ is binner.validation_report_
    assert binner.transform_validation_report_["backend"] == "pyspark"
    assert binner.transform_validation_report_["status"] in {"ok", "warning", "critical"}
    assert binner.transform_validation_report_["summary"]["target_available"] is True
    assert binner.transform_validation_report_["summary"]["n_application_rows"] == 7
    assert str(learned_label) in _bin_counts(profile)
    assert "Missing" not in set(profile["bin_label"].astype(str))
    assert not profile["is_missing_bin"].fillna(False).astype(bool).any()
    assert_frame_equal(binner.reference_profile_, reference_before)
    assert calls
    assert max(call["rows"] for call in calls) <= 20


def test_merge_spark_transform_validate_true_profiles_separate_fallback_missing(spark_session, monkeypatch):
    fit_df = pd.DataFrame({"score": [-5.0, -4.0, 0.0, 3.0, 5.0] * 8, "target": [0, 0, 1, 1, 1] * 8})
    binner = RiskBands(
        max_bins=3,
        min_event_rate_diff=0.0,
        missing_policy="merge",
        missing_merge_criterion="nearest_event_rate",
        missing_merge_fallback="separate_bin",
    ).fit(fit_df, y="target", column="score")
    sdf = _numeric_spark_frame(spark_session, [(None, 0), (float("nan"), 1), (-5.0, 0), (3.0, 1)])
    calls = install_to_pandas_guard(monkeypatch, max_rows=20)

    transformed = binner.transform(sdf, column="score", validate=True)
    profile = binner.application_profile_

    assert transformed.__class__.__module__.startswith("pyspark")
    assert binner.missing_merge_map_ == {}
    assert profile is not None
    assert _bin_counts(profile)["Missing"] == 1
    missing_rows = profile.loc[profile["bin_label"].astype(str) == "Missing"]
    assert len(missing_rows) == 1
    assert int(missing_rows.iloc[0]["n"]) == 2
    assert bool(missing_rows.iloc[0]["is_missing_bin"]) is True
    assert binner.transform_validation_report_["backend"] == "pyspark"
    assert binner.transform_validation_report_["summary"]["target_available"] is True
    assert calls
    assert max(call["rows"] for call in calls) <= 20


def test_merge_spark_transform_validate_true_without_target_skips_profile(spark_session):
    binner, _ = fit_numeric_merge()
    reference_before = binner.reference_profile_.copy()
    sdf = spark_session.createDataFrame(
        [(None,), (float("nan"),), (-5.0,), (0.0,), (5.0,)],
        schema="score double",
    )

    transformed = binner.transform(sdf, column="score", validate=True)

    assert transformed.__class__.__module__.startswith("pyspark")
    assert binner.application_profile_ is None
    assert binner.transform_validation_report_ is binner.validation_report_
    assert binner.transform_validation_report_["validation_type"] == "transform"
    assert binner.transform_validation_report_["status"] == "skipped"
    assert binner.transform_validation_report_["reason"] == "target_not_available"
    assert binner.transform_validation_report_["backend"] == "pyspark"
    assert binner.transform_validation_report_["reference_profile_source"] == "fit_profile"
    assert_frame_equal(binner.reference_profile_, reference_before)
