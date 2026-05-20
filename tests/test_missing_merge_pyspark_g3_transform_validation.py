from collections import Counter

import pytest

from riskbands import RiskBands

pytestmark = pytest.mark.spark
pytest_plugins = ["tests.test_missing_values_pyspark_current_behavior"]


def _numeric_spark_frame(spark_session, rows, *, include_target=True):
    from pyspark.sql import types as T

    fields = [T.StructField("score", T.DoubleType(), True)]
    if include_target:
        fields.append(T.StructField("target", T.IntegerType(), True))
    return spark_session.createDataFrame(rows, schema=T.StructType(fields))


def _fit_rows(n_rows=180):
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


def test_transform_validate_true_builds_application_profile_and_final_merge_bins(spark_session):
    fit_rows = _fit_rows()
    binner = RiskBands(
        max_bins=5,
        min_n_bins=3,
        min_event_rate_diff=0.0,
        sample_size=len(fit_rows),
        missing_policy="merge",
        missing_merge_criterion="nearest_event_rate",
    ).fit(_numeric_spark_frame(spark_session, fit_rows), y="target", column="score", validate=True)
    learned_label = binner.missing_merge_map_["score"]

    app_rows = [(None, 1), (float("nan"), 0), (4.0, 1), (-5.0, 0), (3.0, 1), (-4.0, 0)]
    transformed = binner.transform(
        _numeric_spark_frame(spark_session, app_rows),
        column="score",
        validate=True,
    )
    observed = Counter(row["score"] for row in transformed.select("score").collect())
    report = binner.transform_validation_report_

    assert observed[learned_label] >= 2
    assert binner.application_profile_ is not None
    assert not binner.application_profile_["is_missing_bin"].fillna(False).any()
    assert binner.missing_merge_map_ == {"score": learned_label}
    assert report is binner.validation_report_
    assert report["backend"] == "pyspark"
    assert report["status"] in {"ok", "warning", "critical"}
    assert report["summary"]["target_available"] is True
    assert report["summary"]["n_application_rows"] == len(app_rows)
    assert report["profile_comparison"]


def test_transform_validate_true_without_target_is_skipped_clear(spark_session):
    fit_rows = _fit_rows()
    binner = RiskBands(
        max_bins=4,
        min_n_bins=3,
        min_event_rate_diff=0.0,
        sample_size=len(fit_rows),
        missing_policy="merge",
        missing_merge_criterion="nearest_event_rate",
    ).fit(_numeric_spark_frame(spark_session, fit_rows), y="target", column="score", validate=True)

    binner.transform(
        _numeric_spark_frame(spark_session, [(1.0,), (None,)], include_target=False),
        column="score",
        validate=True,
    )

    report = binner.transform_validation_report_
    assert binner.application_profile_ is None
    assert report["status"] == "skipped"
    assert report["reason"] == "target_not_available"
    assert report["summary"]["target_available"] is False


def test_transform_validation_warns_on_application_share_shift(spark_session):
    fit_rows = _fit_rows()
    binner = RiskBands(
        max_bins=4,
        min_event_rate_diff=0.0,
        sample_size=len(fit_rows),
        missing_policy="merge",
        missing_merge_criterion="nearest_event_rate",
    ).fit(_numeric_spark_frame(spark_session, fit_rows), y="target", column="score", validate=True)
    binner.reference_profile_ = binner.reference_profile_.copy()
    binner.reference_profile_["share"] = 0.2

    app_rows = [(5.0, 1) for _ in range(80)]
    binner.transform(_numeric_spark_frame(spark_session, app_rows), column="score", validate=True)
    report = binner.transform_validation_report_

    assert report["status"] in {"warning", "critical"}
    assert any("application_share_shift" in alert["alert_flags"] for alert in report["alerts"])


def test_transform_validation_does_not_learn_missing_merge_when_fit_sample_had_no_missing(
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
    ).fit(_numeric_spark_frame(spark_session, _fit_rows()), y="target", column="score", validate=True)

    binner.transform(
        _numeric_spark_frame(spark_session, [(None, 1), (float("nan"), 0), (2.0, 1)]),
        column="score",
        validate=True,
    )

    assert binner.missing_merge_map_ == {}
    assert binner.application_profile_["is_missing_bin"].fillna(False).any()
