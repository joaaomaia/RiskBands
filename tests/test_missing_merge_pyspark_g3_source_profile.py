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


def _rows_with_missing(n_rows=240):
    rows = []
    for idx in range(n_rows):
        if idx % 12 == 0:
            score = None
        elif idx % 12 == 1:
            score = float("nan")
        else:
            score = float((idx % 10) - 5)
        target = int(score is None or (score == score and score >= 1.0))
        rows.append((score, target))
    return rows


def test_source_profile_uses_final_bins_and_sample_representativeness(spark_session, monkeypatch):
    rows = _rows_with_missing()
    calls = install_to_pandas_guard(monkeypatch, max_rows=len(rows))

    binner = RiskBands(
        max_bins=4,
        min_event_rate_diff=0.0,
        sample_size=len(rows),
        missing_policy="merge",
        missing_merge_criterion="nearest_event_rate",
    ).fit(_numeric_spark_frame(spark_session, rows), y="target", column="score", validate=True)

    assert binner.source_profile_ is not None
    assert not binner.source_profile_.empty
    assert not binner.source_profile_["is_missing_bin"].fillna(False).any()
    assert binner.reference_profile_source_ == "source_profile"
    assert binner.fit_validation_report_["sample_representativeness"]["status"] in {"ok", "warning"}
    assert binner.fit_validation_report_["sample_representativeness"]["bin_diagnostics"]
    assert calls
    assert max(call["rows"] for call in calls) <= len(rows)


def test_sample_vs_source_reports_missing_bins_and_status_warning(spark_session, monkeypatch):
    rows = _rows_with_missing()

    def sample_without_missing(self, spark_df, *, population_size):
        from pyspark.sql import functions as F

        plan = self._resolve_sampling_plan(population_size=population_size)
        sample = spark_df.filter(F.col("score").isNotNull() & ~F.isnan(F.col("score"))).limit(80)
        plan["sample_size_effective"] = 80
        plan["sample_fraction_effective"] = 80 / population_size
        return sample, plan

    monkeypatch.setattr(RiskBands, "_sample_pyspark_dataframe", sample_without_missing)
    binner = RiskBands(
        max_bins=4,
        min_event_rate_diff=0.0,
        sample_size=80,
        missing_policy="merge",
        missing_merge_criterion="nearest_event_rate",
        missing_merge_fallback="separate_bin",
    ).fit(_numeric_spark_frame(spark_session, rows), y="target", column="score", validate=True)

    report = binner.fit_validation_report_
    assert report["sample_representativeness"]["status"] == "warning"
    assert report["sample_representativeness"]["bins_missing_in_sample"]
    assert any(
        "source_missing_not_seen_in_sample" in row["alert_flags"]
        for row in report["missing_sampling_diagnostics"]
    )


def test_source_profile_guard_records_profile_too_large(spark_session, monkeypatch):
    original_settings = RiskBands._default_validation_settings

    def tiny_profile_limit(self):
        settings = original_settings(self)
        settings["max_profile_rows_to_collect"] = 0
        return settings

    monkeypatch.setattr(RiskBands, "_default_validation_settings", tiny_profile_limit)
    binner = RiskBands(
        max_bins=4,
        min_event_rate_diff=0.0,
        sample_size=60,
        missing_policy="merge",
        missing_merge_criterion="nearest_event_rate",
    ).fit(_numeric_spark_frame(spark_session, _rows_with_missing(120)), y="target", column="score", validate=True)

    report = binner.fit_validation_report_
    assert binner.source_profile_ is None
    assert report["summary"]["source_profile_status"] == "skipped_profile_too_large"
    assert any("profile_too_large" in alert["alert_flags"] for alert in report["alerts"])
