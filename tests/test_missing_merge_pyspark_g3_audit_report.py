import pytest

from riskbands import RiskBands
from riskbands.audit_report import build_audit_report_context

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


def _rows(n_rows=160):
    rows = []
    for idx in range(n_rows):
        if idx % 10 == 0:
            score = None
        elif idx % 10 == 1:
            score = float("nan")
        else:
            score = float((idx % 12) - 6)
        rows.append((score, int(score is None or (score == score and score >= 1.0))))
    return rows


def test_audit_report_context_exposes_missing_sampling_diagnostics(spark_session):
    rows = _rows()
    binner = RiskBands(
        max_bins=4,
        min_event_rate_diff=0.0,
        sample_size=len(rows),
        missing_policy="merge",
        missing_merge_criterion="nearest_event_rate",
    ).fit(_numeric_spark_frame(spark_session, rows), y="target", column="score", validate=True)

    context = build_audit_report_context(binner)

    assert context["missing_sampling_diagnostics"][0]["variable"] == "score"
    assert context["validation"]["missing_sampling_diagnostics"][0]["variable"] == "score"
    assert any("Fit sampled-to-pandas" in item for item in context["limitations"])
    assert any("Merge decision learned on sample" in item for item in context["limitations"])


def test_audit_report_does_not_claim_merge_learned_when_sample_missed_source_missing(
    spark_session, monkeypatch, tmp_path
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
    ).fit(_numeric_spark_frame(spark_session, _rows()), y="target", column="score", validate=True)

    report_path = tmp_path / "custom_g3_audit.html"
    binner.export_audit_report(report_path, title="Custom G3 Audit")
    html = report_path.read_text(encoding="utf-8")

    assert report_path.name == "custom_g3_audit.html"
    assert "Custom G3 Audit" in html
    assert "No merge decision learned on sample" in html
    assert "Source missing not seen in sample" in html
    assert "Merge decision learned on sample:" not in html
