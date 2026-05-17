import pandas as pd
from pandas.testing import assert_frame_equal

from riskbands import RiskBands
from riskbands.reporting import load_bundle_metadata
from tests.test_fit_validate_true import ValidatingFakeSparkDataFrame, make_frame, patch_fake_pyspark


def fit_binner():
    df = make_frame()
    binner = RiskBands(strategy="supervised", max_bins=4, min_event_rate_diff=0.0)
    binner.fit(df, y="target", column="score")
    return binner, df


def test_transform_validate_true_returns_pandas_dataframe_and_same_bins():
    binner, df = fit_binner()
    application = df[["score", "target"]].copy()

    base = binner.transform(application[["score"]])
    validated = binner.transform(application, validate=True)

    assert isinstance(validated, pd.DataFrame)
    assert_frame_equal(validated, base)
    assert binner.validation_report_["validation_type"] == "transform"


def test_transform_validate_true_without_target_does_not_break():
    binner, df = fit_binner()

    transformed = binner.transform(df[["score"]], validate=True)

    assert isinstance(transformed, pd.DataFrame)
    assert binner.application_profile_ is None
    assert binner.validation_report_["status"] == "skipped"
    assert binner.validation_report_["reason"] == "target_not_available"


def test_transform_validate_true_with_target_builds_application_profile_and_compares_reference():
    binner, df = fit_binner()

    binner.transform(df[["score", "target"]], validate=True)

    assert binner.application_profile_ is not None
    assert not binner.application_profile_.empty
    assert binner.validation_report_["reference_profile_source"] == "fit_profile"
    assert binner.validation_report_["summary"]["n_application_rows"] == len(df)


def test_transform_validate_true_preserves_fit_report_and_sets_transform_report():
    df = make_frame()
    binner = RiskBands(strategy="supervised", max_bins=4, min_event_rate_diff=0.0)
    binner.fit(df, y="target", column="score", validate=True)
    fit_report = binner.fit_validation_report_

    binner.transform(df[["score", "target"]], validate=True)

    assert binner.fit_validation_report_ is fit_report
    assert binner.transform_validation_report_ is binner.validation_report_
    assert binner.fit_validation_report_["validation_type"] == "fit"
    assert binner.transform_validation_report_["validation_type"] == "transform"


def test_multivariable_validation_reports_use_real_row_counts():
    df = make_frame(n=100)
    df["score_2"] = -df["score"]
    binner = RiskBands(strategy="supervised", max_bins=3, min_event_rate_diff=0.0)

    binner.fit(df, y="target", columns=["score", "score_2"], validate=True)
    binner.transform(df[["score", "score_2", "target"]], validate=True)

    assert binner.fit_validation_report_["summary"]["n_rows_fit"] == len(df)
    assert binner.fit_validation_report_["summary"]["n_variables"] == 2
    assert binner.transform_validation_report_["summary"]["n_application_rows"] == len(df)
    assert binner.transform_validation_report_["summary"]["n_variables"] == 2


def test_transform_validate_true_and_false_produce_same_series_output():
    binner, df = fit_binner()

    base = binner.transform(df["score"])
    validated = binner.transform(df[["score", "target"]], column="score", return_type="series", validate=True)

    assert base.equals(validated)


def test_transform_validate_true_returns_spark_dataframe(monkeypatch):
    patch_fake_pyspark(monkeypatch)
    binner, df = fit_binner()
    spark_df = ValidatingFakeSparkDataFrame(df[["score", "target"]])

    transformed = binner.transform(spark_df, validate=True)

    assert isinstance(transformed, ValidatingFakeSparkDataFrame)
    assert transformed.columns == ["score"]
    assert binner.application_profile_ is not None
    assert binner.validation_report_["backend"] == "pyspark"


def test_transform_spark_validate_false_does_not_collect_validation_profiles(monkeypatch):
    patch_fake_pyspark(monkeypatch)
    binner, df = fit_binner()
    spark_df = ValidatingFakeSparkDataFrame(df[["score", "target"]])

    binner.transform(spark_df, validate=False)

    assert spark_df.ops["to_pandas_columns"] == []


def test_transform_validate_true_uses_reference_loaded_from_bundle(tmp_path):
    binner, df = fit_binner()
    binner.export_bundle(tmp_path / "bundle")
    loaded = load_bundle_metadata(tmp_path / "bundle")
    binner.reference_profile_ = pd.DataFrame(loaded["reference_profile"])
    binner.reference_profile_source_ = loaded["reference_profile_source"]

    transformed = binner.transform(df[["score", "target"]], validate=True)

    assert isinstance(transformed, pd.DataFrame)
    assert binner.validation_report_["reference_profile_source"] == "fit_profile"
    assert binner.validation_report_["status"] in {"ok", "warning"}
