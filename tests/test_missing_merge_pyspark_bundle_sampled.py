import json

import pandas as pd
import pytest

from riskbands import RiskBands
from riskbands.reporting import load_bundle
from riskbands.utils import dataframe_backend
from tests.test_fit_validate_true import ValidatingFakeSparkDataFrame

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


def _fit_rows():
    rows = []
    for _ in range(6):
        rows.extend(
            [
                (-5.0, 0),
                (-3.0, 0),
                (0.0, 1),
                (3.0, 1),
                (None, 0),
                (float("nan"), 1),
            ]
        )
    return rows


def test_bundle_load_and_audit_report_preserve_sampled_fit_caveat(spark_session, tmp_path):
    rows = _fit_rows()
    binner = RiskBands(
        max_bins=3,
        min_event_rate_diff=0.0,
        sample_size=len(rows),
        missing_policy="merge",
        missing_merge_criterion="nearest_event_rate",
    ).fit(_numeric_spark_frame(spark_session, rows), y="target", column="score")
    learned_label = binner.missing_merge_map_["score"]

    bundle_dir = tmp_path / "bundle"
    binner.export_bundle(bundle_dir)
    loaded = load_bundle(bundle_dir)
    manifest = json.loads((bundle_dir / "metadata.json").read_text(encoding="utf-8"))
    html = (bundle_dir / "audit_report.html").read_text(encoding="utf-8")

    assert (bundle_dir / "missing_decision_log.csv").exists()
    assert (bundle_dir / "missing_profile.csv").exists()
    assert (bundle_dir / "missing_merge_candidates.csv").exists()
    assert manifest["metadata"]["backend_metadata"]["fit_mode"] == "sampled_to_pandas"
    assert manifest["metadata"]["sampling_metadata"]["merge_decision_learned_on_sample"] is True
    assert manifest["metadata"]["sampling_caveat"] == binner.sampling_metadata_["sampling_caveat"]
    assert loaded["manifest"]["metadata"]["sampling_metadata"]["sampling_caveat"] == binner.sampling_metadata_[
        "sampling_caveat"
    ]
    assert loaded["missing_decision_log"][0]["sampling_caveat"] == binner.sampling_metadata_["sampling_caveat"]
    assert "sampled-to-pandas" in html
    assert "full Spark DataFrame" in html

    output = binner.transform(
        _numeric_spark_frame(spark_session, [(None, 1), (float("nan"), 0), (-5.0, 0)]),
        column="score",
    )
    observed = [row["score"] for row in output.select("score").collect()]
    assert observed.count(learned_label) >= 2


def test_bundle_and_audit_report_do_not_claim_merge_learned_when_sample_has_no_missing(
    monkeypatch, tmp_path
):
    pdf = pd.DataFrame(
        {
            "score": [-4.0, -3.0, -2.0, -1.0, 1.0, 2.0, None, float("nan")],
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

    bundle_dir = tmp_path / "bundle"
    binner.export_bundle(bundle_dir)
    loaded = load_bundle(bundle_dir)
    manifest = json.loads((bundle_dir / "metadata.json").read_text(encoding="utf-8"))
    html = (bundle_dir / "audit_report.html").read_text(encoding="utf-8")

    sampling_metadata = manifest["metadata"]["sampling_metadata"]
    assert binner.missing_merge_map_ == {}
    assert sampling_metadata["fit_mode"] == "sampled_to_pandas"
    assert sampling_metadata["sampling_applied"] is True
    assert sampling_metadata["merge_decision_learned_on_sample"] is False
    assert sampling_metadata["merge_decision_count"] == 0
    assert sampling_metadata["merge_decision_variables"] == []
    assert manifest["metadata"]["merge_decision_learned_on_sample"] is False
    assert manifest["metadata"]["merge_decision_count"] == 0
    assert loaded["missing_merge_map"] == {}
    assert loaded["missing_decision_log"][0]["action"] == "no_missing_detected"
    assert loaded["missing_decision_log"][0]["merge_decision_learned_on_sample"] is False
    assert "sampled-to-pandas" in html
    assert "merge decision learned on sample" in html
    assert "Nenhum destino de merge foi aprendido" in html
    assert "A decisão foi aprendida no fit" not in html


def test_bundle_boundary_loaded_payload_is_metadata_not_rehydrated_model(spark_session, tmp_path):
    rows = _fit_rows()
    binner = RiskBands(
        max_bins=3,
        min_event_rate_diff=0.0,
        sample_size=len(rows),
        missing_policy="merge",
        missing_merge_criterion="nearest_woe",
    ).fit(_numeric_spark_frame(spark_session, rows), y="target", column="score")

    bundle_dir = tmp_path / "bundle"
    binner.export_bundle(bundle_dir)
    loaded = load_bundle(bundle_dir)

    assert isinstance(loaded, dict)
    assert "transform" not in loaded
    assert loaded["missing_merge_map"] == binner.missing_merge_map_
    assert loaded["manifest"]["metadata"]["merge_decision_fit_mode"] == "sampled_to_pandas"
