import json

import pytest

from riskbands import RiskBands
from riskbands.reporting import load_bundle

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


def _rows_with_missing(n_rows=180):
    rows = []
    for idx in range(n_rows):
        if idx % 10 == 0:
            score = None
        elif idx % 10 == 1:
            score = float("nan")
        else:
            score = float((idx % 12) - 6)
        target = int(score is None or (score == score and score >= 1.0))
        rows.append((score, target))
    return rows


def _rows_without_missing(n_rows=120):
    rows = []
    for idx in range(n_rows):
        score = float((idx % 12) - 6)
        rows.append((score, int(score >= 1.0)))
    return rows


def _diagnostic_for_score(binner):
    diagnostics = binner.fit_validation_report_["missing_sampling_diagnostics"]
    return next(row for row in diagnostics if row["variable"] == "score")


def test_missing_sampling_diagnostics_when_missing_is_in_sample_and_source(spark_session):
    rows = _rows_with_missing()
    binner = RiskBands(
        max_bins=4,
        min_event_rate_diff=0.0,
        sample_size=len(rows),
        missing_policy="merge",
        missing_merge_criterion="nearest_event_rate",
    ).fit(_numeric_spark_frame(spark_session, rows), y="target", column="score", validate=True)

    diagnostic = _diagnostic_for_score(binner)
    assert diagnostic["missing_count_sample_fit"] == diagnostic["missing_count_source_spark"]
    assert diagnostic["missing_share_abs_diff"] == pytest.approx(0.0)
    assert diagnostic["merge_decision_learned_on_sample"] is True
    assert diagnostic["missing_merge_destination_learned"] is not None
    assert diagnostic["fallback_risk"] is False
    assert diagnostic["status"] == "ok"


def test_missing_sampling_diagnostics_warns_when_source_missing_is_not_sampled(
    spark_session, monkeypatch
):
    def sample_without_missing(self, spark_df, *, population_size):
        from pyspark.sql import functions as F

        plan = self._resolve_sampling_plan(population_size=population_size)
        sample = spark_df.filter(F.col("score").isNotNull() & ~F.isnan(F.col("score"))).limit(60)
        plan["sample_size_effective"] = 60
        plan["sample_fraction_effective"] = 60 / population_size
        return sample, plan

    monkeypatch.setattr(RiskBands, "_sample_pyspark_dataframe", sample_without_missing)
    binner = RiskBands(
        max_bins=4,
        min_event_rate_diff=0.0,
        sample_size=60,
        missing_policy="merge",
        missing_merge_criterion="nearest_event_rate",
        missing_merge_fallback="separate_bin",
    ).fit(_numeric_spark_frame(spark_session, _rows_with_missing()), y="target", column="score", validate=True)

    diagnostic = _diagnostic_for_score(binner)
    assert diagnostic["missing_count_sample_fit"] == 0
    assert diagnostic["missing_count_source_spark"] > 0
    assert diagnostic["merge_decision_learned_on_sample"] is False
    assert diagnostic["fallback_risk"] is True
    assert diagnostic["status"] == "warning"
    assert "source_missing_not_seen_in_sample" in diagnostic["alert_flags"]
    assert "merge_decision_not_learned_but_source_has_missing" in diagnostic["alert_flags"]
    assert binner.fit_validation_report_["summary"]["missing_sampling_status"] == "warning"
    assert binner.metadata_["missing_sampling_diagnostics"][0]["variable"] == "score"


def test_missing_sampling_diagnostics_when_source_has_no_missing(spark_session):
    rows = _rows_without_missing()
    binner = RiskBands(
        max_bins=4,
        min_event_rate_diff=0.0,
        sample_size=len(rows),
        missing_policy="merge",
        missing_merge_criterion="nearest_event_rate",
    ).fit(_numeric_spark_frame(spark_session, rows), y="target", column="score", validate=True)

    diagnostic = _diagnostic_for_score(binner)
    assert diagnostic["missing_count_sample_fit"] == 0
    assert diagnostic["missing_count_source_spark"] == 0
    assert diagnostic["merge_decision_learned_on_sample"] is False
    assert diagnostic["fallback_risk"] is False
    assert diagnostic["status"] == "ok"


def test_missing_sampling_diagnostics_are_exported_in_bundle(spark_session, tmp_path):
    rows = _rows_with_missing()
    binner = RiskBands(
        max_bins=4,
        min_event_rate_diff=0.0,
        sample_size=len(rows),
        missing_policy="merge",
        missing_merge_criterion="nearest_event_rate",
    ).fit(_numeric_spark_frame(spark_session, rows), y="target", column="score", validate=True)

    bundle_dir = tmp_path / "bundle"
    binner.export_bundle(bundle_dir)
    manifest = json.loads((bundle_dir / "metadata.json").read_text(encoding="utf-8"))
    loaded = load_bundle(bundle_dir)

    assert manifest["metadata"]["missing_sampling_diagnostics"][0]["variable"] == "score"
    assert manifest["missing_sampling_diagnostics"][0]["variable"] == "score"
    assert loaded["missing_sampling_diagnostics"][0]["variable"] == "score"
