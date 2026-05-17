import numpy as np
import pandas as pd
import pytest

from riskbands import RiskBands


def make_numeric_missing_frame():
    score = np.array([-5, -4, -3, -2, -1, 0, 1, 2, 3, 4, np.nan, np.nan] * 8, dtype=float)
    target = np.array([0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 0] * 8, dtype=int)
    return pd.DataFrame({"score": score, "target": target})


def make_categorical_missing_frame():
    return pd.DataFrame(
        {
            "grade": ["A", "A", "A", "B", "B", "C", "C", None, np.nan, "D", "D", "E"] * 8,
            "target": [0, 0, 0, 1, 1, 1, 0, 1, 0, 1, 1, 0] * 8,
        }
    )


def fit_numeric_missing_binner(validate=False):
    df = make_numeric_missing_frame()
    binner = RiskBands(strategy="supervised", max_bins=3, min_event_rate_diff=0.0)
    binner.fit(df, y="target", column="score", validate=validate)
    return binner, df


def fit_categorical_missing_binner(validate=False):
    df = make_categorical_missing_frame()
    binner = RiskBands(
        strategy="supervised",
        max_bins=4,
        min_event_rate_diff=0.0,
        force_categorical=["grade"],
    )
    binner.fit(df, y="target", column="grade", validate=validate)
    return binner, df


def test_numeric_pandas_nan_transforms_to_missing_and_profile_is_explicit():
    binner, df = fit_numeric_missing_binner()

    transformed = binner.transform(df[["score"]])
    missing_mask = df["score"].isna()
    profile = binner.fit_profile_
    missing_profile = profile.loc[profile["is_missing_bin"]]

    assert set(transformed.loc[missing_mask, "score"]) == {"Missing"}
    assert len(missing_profile) == 1

    row = missing_profile.iloc[0]
    assert row["bin_label"] == "Missing"
    assert int(row["n"]) == int(missing_mask.sum())
    assert row["events"] == pytest.approx(float(df.loc[missing_mask, "target"].sum()))
    assert row["event_rate"] == pytest.approx(0.5)
    assert row["share"] == pytest.approx(missing_mask.mean())
    assert bool(row["is_regular_bin"]) is False


def test_numeric_pandas_bin_summary_filters_missing_even_when_profile_has_it():
    binner, _ = fit_numeric_missing_binner()

    bin_labels = binner.bin_summary["bin"].astype(str).str.strip().str.lower()
    profile_labels = binner.fit_profile_["bin_label"].astype(str)

    assert "Missing" in set(profile_labels)
    assert not bin_labels.eq("missing").any()
    assert not bin_labels.str.startswith("missing").any()


def test_categorical_pandas_missing_uses_internal_token_but_maps_to_regular_bin():
    binner, df = fit_categorical_missing_binner()

    mapping = binner.get_bin_mapping("grade")
    mapping_by_category = dict(zip(mapping["categoria"].astype(str), mapping["bin"], strict=False))
    transformed = binner.transform(df[["grade"]])
    missing_mask = df["grade"].isna()
    missing_bin = mapping_by_category["_MISSING_"]

    assert "_MISSING_" in mapping_by_category
    assert "_UNKNOWN_" in mapping_by_category
    assert mapping_by_category["_UNKNOWN_"] != missing_bin
    assert set(transformed.loc[missing_mask, "grade"]) == {missing_bin}
    assert str(missing_bin).lower() != "missing"

    missing_profile_rows = binner.fit_profile_.loc[binner.fit_profile_["is_missing_bin"]]
    regular_profile = binner.fit_profile_.loc[binner.fit_profile_["bin_label"].astype(str) == str(missing_bin)]
    assert missing_profile_rows.empty
    assert len(regular_profile) == 1
    assert bool(regular_profile.iloc[0]["is_regular_bin"]) is True


def test_categorical_pandas_missing_and_unknown_are_deterministic_and_distinct():
    binner, _ = fit_categorical_missing_binner()
    mapping = binner.get_bin_mapping("grade")
    mapping_by_category = dict(zip(mapping["categoria"].astype(str), mapping["bin"], strict=False))

    probe = pd.DataFrame({"grade": [None, np.nan, "Z", "B"]})
    transformed_first = binner.transform(probe)
    transformed_second = binner.transform(probe)

    assert transformed_first.equals(transformed_second)
    assert transformed_first.loc[0, "grade"] == mapping_by_category["_MISSING_"]
    assert transformed_first.loc[1, "grade"] == mapping_by_category["_MISSING_"]
    assert transformed_first.loc[2, "grade"] == mapping_by_category["_UNKNOWN_"]
    assert transformed_first.loc[2, "grade"] != transformed_first.loc[0, "grade"]
