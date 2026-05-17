import numpy as np
import pandas as pd

from riskbands import RiskBands
from tests.test_missing_values_current_behavior import (
    fit_categorical_missing_binner,
    make_categorical_missing_frame,
    make_numeric_missing_frame,
)


def test_separate_bin_numeric_missing_is_explicit_in_profile_and_summary():
    df = make_numeric_missing_frame()
    binner = RiskBands(max_bins=3, min_event_rate_diff=0.0, missing_policy="separate_bin")

    binner.fit(df, y="target", column="score", validate=True)

    transformed = binner.transform(df[["score"]])
    missing_profile = binner.fit_profile_.loc[binner.fit_profile_["is_missing_bin"]]
    assert set(transformed.loc[df["score"].isna(), "score"]) == {"Missing"}
    assert len(missing_profile) == 1
    assert "Missing" in set(binner.bin_summary["bin"].astype(str))
    assert binner.fit_validation_report_["summary"]["variables_with_missing_bins"] == 1


def test_separate_bin_categorical_missing_does_not_use_regular_default_bin():
    df = make_categorical_missing_frame()
    binner = RiskBands(
        max_bins=4,
        min_event_rate_diff=0.0,
        force_categorical=["grade"],
        missing_policy="separate_bin",
    )

    binner.fit(df, y="target", column="grade", validate=True)
    transformed = binner.transform(df[["grade"]])

    assert set(transformed.loc[df["grade"].isna(), "grade"]) == {"Missing"}
    missing_profile = binner.fit_profile_.loc[binner.fit_profile_["is_missing_bin"]]
    assert len(missing_profile) == 1
    assert bool(missing_profile.iloc[0]["is_regular_bin"]) is False
    assert "Missing" in set(binner.get_bin_mapping("grade")["bin"].astype(str))
    regular_labels = set(binner.fit_profile_.loc[binner.fit_profile_["is_regular_bin"], "bin_label"].astype(str))
    assert "Missing" not in regular_labels


def test_separate_bin_categorical_new_missing_in_transform_validate_is_visible():
    df = pd.DataFrame({"grade": ["A", "B", "C", "D"] * 10, "target": [0, 1, 1, 0] * 10})
    binner = RiskBands(
        max_bins=4,
        min_event_rate_diff=0.0,
        force_categorical=["grade"],
        missing_policy="separate_bin",
    ).fit(df, y="target", column="grade", validate=True)
    app = pd.DataFrame({"grade": [None, np.nan, "A", "Z"], "target": [1, 0, 0, 1]})

    transformed = binner.transform(app, column="grade", validate=True)
    missing_profile = binner.application_profile_.loc[binner.application_profile_["is_missing_bin"]]

    assert transformed.loc[[0, 1], "grade"].tolist() == ["Missing", "Missing"]
    assert len(missing_profile) == 1
    assert int(missing_profile.iloc[0]["n"]) == 2
    assert binner.transform_validation_report_["summary"]["variables_with_missing_bins"] == 1


def test_standard_categorical_missing_behavior_remains_current():
    standard, df = fit_categorical_missing_binner()
    explicit_standard = RiskBands(
        max_bins=4,
        min_event_rate_diff=0.0,
        force_categorical=["grade"],
        missing_policy="standard",
    ).fit(df, y="target", column="grade")

    assert explicit_standard.transform(df[["grade"]]).equals(standard.transform(df[["grade"]]))
    assert explicit_standard.fit_profile_.loc[explicit_standard.fit_profile_["is_missing_bin"]].empty


def test_separate_bin_decision_log_records_training_only_action():
    df = make_categorical_missing_frame()
    binner = RiskBands(
        force_categorical=["grade"],
        missing_policy="separate_bin",
        min_event_rate_diff=0.0,
    ).fit(df, y="target", column="grade")

    row = binner.missing_decision_log_.iloc[0]

    assert row["variable"] == "grade"
    assert row["action"] == "separate_bin_created"
    assert bool(row["training_only"]) is True
    assert binner.missing_profile_.iloc[0]["bin_label"] == "Missing"
