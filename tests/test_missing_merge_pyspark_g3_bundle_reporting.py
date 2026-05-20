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


def test_bundle_preserves_sample_source_metadata_and_missing_diagnostics(spark_session, tmp_path):
    rows = _rows()
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

    assert manifest["metadata"]["sampling_metadata"]["fit_mode"] == "sampled_to_pandas"
    assert manifest["metadata"]["source_missing_counts"]["score"] > 0
    assert manifest["metadata"]["missing_sampling_diagnostics"][0]["variable"] == "score"
    assert manifest["missing_sampling_diagnostics"][0]["variable"] == "score"
    assert loaded["missing_sampling_diagnostics"][0]["variable"] == "score"
    assert loaded["fit_validation_report"]["missing_sampling_diagnostics"][0]["variable"] == "score"


def test_bundle_report_html_contains_sampling_caveats_for_learned_merge(spark_session, tmp_path):
    rows = _rows()
    binner = RiskBands(
        max_bins=4,
        min_event_rate_diff=0.0,
        sample_size=len(rows),
        missing_policy="merge",
        missing_merge_criterion="nearest_event_rate",
    ).fit(_numeric_spark_frame(spark_session, rows), y="target", column="score", validate=True)

    bundle_dir = tmp_path / "bundle"
    binner.export_bundle(bundle_dir)
    html = (bundle_dir / "audit_report.html").read_text(encoding="utf-8")

    assert "sampled-to-pandas" in html
    assert "Fit sampled-to-pandas" in html
    assert "Merge decision learned on sample" in html
    assert "Missing sampling diagnostics" in html
