import pytest

from riskbands import RiskBands
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


def _rows():
    rows = []
    for idx in range(72):
        if idx % 9 == 0:
            score = None
        elif idx % 10 == 0:
            score = float("nan")
        else:
            score = float((idx % 11) - 5)
        target = int((idx % 11) >= 5 or score is None)
        rows.append((score, target))
    return rows


@pytest.mark.parametrize("criterion", ["nearest_event_rate", "nearest_woe"])
def test_fit_spark_merge_validate_true_builds_minimal_reports(spark_session, monkeypatch, criterion):
    rows = _rows()
    sdf = _numeric_spark_frame(spark_session, rows).repartition(2)
    calls = install_to_pandas_guard(monkeypatch, max_rows=len(rows))

    binner = RiskBands(
        max_bins=4,
        min_event_rate_diff=0.0,
        sample_size=len(rows),
        missing_policy="merge",
        missing_merge_criterion=criterion,
    ).fit(sdf, y="target", column="score", validate=True)

    assert binner.fit_validation_report_ is binner.validation_report_
    assert binner.fit_validation_report_["validation_type"] == "fit"
    assert binner.fit_validation_report_["backend"] == "pyspark"
    assert binner.fit_validation_report_["fit_mode"] == "sampled_to_pandas"
    assert binner.fit_validation_report_["sampling_applied"] is True
    assert binner.fit_validation_report_["sample_size_requested"] == len(rows)
    assert binner.fit_validation_report_["sample_fraction_effective"] == 1.0
    assert binner.fit_validation_report_["summary"]["n_rows_source"] == len(rows)
    assert binner.fit_validation_report_["summary"]["n_rows_fit"] == len(rows)
    assert binner.fit_validation_report_["summary"]["source_profile_status"] == "computed"
    assert binner.fit_validation_report_["summary"]["sample_representativeness_status"] in {
        "ok",
        "warning",
        "critical",
    }
    assert binner.fit_validation_report_["missing_sampling_diagnostics"]
    assert binner.fit_validation_report_["merge_decision_summary"]["merge_decision_count"] >= 1
    assert binner.fit_validation_report_["merge_decision_summary"]["fit_mode"] == "sampled_to_pandas"
    assert binner.source_profile_ is not None
    assert not binner.source_profile_.empty
    assert binner.reference_profile_ is not None
    assert binner.reference_profile_source_ == "source_profile"
    assert binner.sampling_metadata_["merge_decision_learned_on_sample"] is True
    assert calls
    assert max(call["rows"] for call in calls) <= len(rows)
