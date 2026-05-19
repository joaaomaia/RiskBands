import pandas as pd
import pytest

from riskbands import RiskBands
from tests.test_missing_values_current_behavior import make_numeric_missing_frame
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


def test_merge_spark_fit_nearest_event_rate_is_sampled_to_pandas(spark_session):
    rows = [(float(idx % 7), int(idx % 2 == 0)) for idx in range(28)]
    rows.extend([(None, 1), (float("nan"), 0)])
    sdf = _numeric_spark_frame(spark_session, rows)

    binner = RiskBands(
        sample_size=len(rows),
        min_event_rate_diff=0.0,
        missing_policy="merge",
        missing_merge_criterion="nearest_event_rate",
    ).fit(sdf, y="target", column="score")

    assert binner.input_backend_ == "pyspark"
    assert binner.fit_backend_ == "pandas_core"
    assert binner.backend_metadata_["fit_mode"] == "sampled_to_pandas"
    assert binner.sampling_metadata_["merge_decision_learned_on_sample"] is True
    assert binner.missing_merge_map_["score"]


def test_merge_spark_fit_nearest_woe_is_sampled_to_pandas(spark_session):
    rows = [(float(idx % 7), int(idx % 3 == 0)) for idx in range(28)]
    rows.extend([(None, 1), (float("nan"), 0)])
    sdf = _numeric_spark_frame(spark_session, rows)

    binner = RiskBands(
        sample_size=len(rows),
        min_event_rate_diff=0.0,
        missing_policy="merge",
        missing_merge_criterion="nearest_woe",
    ).fit(sdf, y="target", column="score")

    assert binner.input_backend_ == "pyspark"
    assert binner.fit_backend_ == "pandas_core"
    assert binner.backend_metadata_["fit_mode"] == "sampled_to_pandas"
    assert binner.sampling_metadata_["merge_decision_learned_on_sample"] is True
    assert binner.missing_merge_map_["score"]


@pytest.mark.parametrize("criterion", ["nearest_event_rate", "nearest_woe"])
def test_merge_spark_boundary_records_sampling_caveat(spark_session, criterion):
    rows = [(float(idx % 5), int(idx % 2 == 0)) for idx in range(18)]
    rows.extend([(None, 1), (float("nan"), 0)])
    sdf = _numeric_spark_frame(spark_session, rows)

    binner = RiskBands(
        sample_size=len(rows),
        min_event_rate_diff=0.0,
        missing_policy="merge",
        missing_merge_criterion=criterion,
    ).fit(sdf, y="target", column="score")

    caveat = binner.sampling_metadata_["sampling_caveat"]
    assert "sampled-to-pandas" in caveat
    assert binner.missing_decision_log_["merge_decision_learned_on_sample"].eq(True).all()
    assert binner.missing_decision_log_["sampling_caveat"].eq(caveat).all()


def test_merge_pandas_fit_spark_transform_is_allowed(spark_session):
    binner = RiskBands(
        missing_policy="merge",
        missing_merge_criterion="nearest_event_rate",
        min_event_rate_diff=0.0,
    ).fit(make_numeric_missing_frame(), y="target", column="score")
    sdf = _numeric_spark_frame(spark_session, [(1.0, 0), (None, 1)])

    transformed = binner.transform(sdf, column="score")

    assert transformed.__class__.__module__.startswith("pyspark")
    assert "Missing" not in transformed.toPandas()["score"].tolist()


def test_merge_nearest_woe_pandas_fit_spark_transform_is_allowed(spark_session):
    binner = RiskBands(
        missing_policy="merge",
        missing_merge_criterion="nearest_woe",
        min_event_rate_diff=0.0,
    ).fit(make_numeric_missing_frame(), y="target", column="score")
    sdf = _numeric_spark_frame(spark_session, [(1.0, 0), (None, 1)])

    transformed = binner.transform(sdf, column="score")

    assert transformed.__class__.__module__.startswith("pyspark")
    assert "Missing" not in transformed.toPandas()["score"].tolist()


def test_separate_bin_spark_transform_still_works(spark_session):
    binner = RiskBands(
        missing_policy="separate_bin",
        min_event_rate_diff=0.0,
    ).fit(make_numeric_missing_frame(), y="target", column="score")
    sdf = _numeric_spark_frame(spark_session, [(1.0, 0), (None, 1), (float("nan"), 0)])

    transformed = binner.transform(sdf, column="score")
    observed = transformed.toPandas()["score"].tolist()

    assert transformed.__class__.__module__.startswith("pyspark")
    assert observed.count("Missing") == 2


def test_separate_bin_spark_validate_still_uses_bounded_native_profile(spark_session, monkeypatch):
    rows = []
    for idx in range(90):
        score = None if idx % 13 == 0 else float((idx % 9) - 4)
        target = int(idx % 4 == 0 or score is None)
        rows.append((score, target))
    sdf = _numeric_spark_frame(spark_session, rows).repartition(2)
    binner = RiskBands(
        missing_policy="separate_bin",
        min_event_rate_diff=0.0,
        sample_size=90,
    ).fit(sdf, y="target", column="score", validate=True)
    calls = install_to_pandas_guard(monkeypatch, max_rows=30)

    transformed = binner.transform(sdf, column="score", validate=True)
    missing_rows = binner.application_profile_.loc[binner.application_profile_["is_missing_bin"]]

    assert transformed.__class__.__module__.startswith("pyspark")
    assert calls
    assert max(call["rows"] for call in calls) <= 30
    assert len(missing_rows) == 1
    assert missing_rows.iloc[0]["bin_label"] == "Missing"
    assert binner.transform_validation_report_["backend"] == "pyspark"


def test_forbid_spark_transform_still_enforces_missing_policy(spark_session):
    fit_df = pd.DataFrame({"score": [1.0, 2.0, 3.0, 4.0] * 4, "target": [0, 0, 1, 1] * 4})
    binner = RiskBands(
        missing_policy="forbid",
        min_event_rate_diff=0.0,
    ).fit(fit_df, y="target", column="score")
    sdf = _numeric_spark_frame(spark_session, [(1.0, 0), (None, 1)])

    with pytest.raises(ValueError, match="missing_policy='forbid'.*pyspark.*score=1"):
        binner.transform(sdf, column="score")
