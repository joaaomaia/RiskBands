import pandas as pd
import pytest

from tests.test_missing_values_current_behavior import (
    fit_categorical_missing_binner,
    fit_numeric_missing_binner,
)


def _single_missing_profile_row(profile):
    rows = profile.loc[profile["is_missing_bin"]]
    assert len(rows) == 1
    return rows.iloc[0]


def test_fit_validate_true_numeric_missing_registers_missing_profile():
    binner, df = fit_numeric_missing_binner(validate=True)

    row = _single_missing_profile_row(binner.fit_profile_)

    assert binner.fit_validation_report_["validation_type"] == "fit"
    assert binner.validation_report_ is binner.fit_validation_report_
    assert binner.fit_validation_report_["summary"]["n_fit_profile_rows"] == len(binner.fit_profile_)
    assert row["bin_label"] == "Missing"
    assert int(row["n"]) == int(df["score"].isna().sum())
    assert row["events"] == pytest.approx(float(df.loc[df["score"].isna(), "target"].sum()))


def test_transform_validate_true_numeric_missing_registers_application_profile_without_overwriting_fit_report():
    binner, _ = fit_numeric_missing_binner(validate=True)
    fit_report = binner.fit_validation_report_
    app = pd.DataFrame(
        {
            "score": [float("nan"), -5.0, 0.0, 4.0, float("nan"), 2.0],
            "target": [1, 0, 0, 1, 0, 1],
        }
    )

    transformed = binner.transform(app, column="score", validate=True)
    row = _single_missing_profile_row(binner.application_profile_)

    assert transformed.loc[[0, 4], "score"].tolist() == ["Missing", "Missing"]
    assert binner.fit_validation_report_ is fit_report
    assert binner.transform_validation_report_ is binner.validation_report_
    assert binner.transform_validation_report_["validation_type"] == "transform"
    assert binner.transform_validation_report_["summary"]["n_application_rows"] == len(app)
    assert row["bin_label"] == "Missing"
    assert int(row["n"]) == 2
    assert row["events"] == pytest.approx(1.0)
    assert row["event_rate"] == pytest.approx(0.5)


def test_categorical_missing_profile_is_regular_current_behavior():
    binner, df = fit_categorical_missing_binner(validate=True)
    mapping = binner.get_bin_mapping("grade")
    mapping_by_category = dict(zip(mapping["categoria"].astype(str), mapping["bin"], strict=False))
    missing_bin = mapping_by_category["_MISSING_"]
    missing_mask = df["grade"].isna()

    assert binner.fit_profile_.loc[binner.fit_profile_["is_missing_bin"]].empty

    row = binner.fit_profile_.loc[
        binner.fit_profile_["bin_label"].astype(str) == str(missing_bin)
    ].iloc[0]
    assert bool(row["is_regular_bin"]) is True
    assert int(row["n"]) >= int(missing_mask.sum())
    assert str(row["bin_label"]).lower() != "missing"
