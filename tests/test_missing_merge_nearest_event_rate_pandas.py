import numpy as np
import pandas as pd
import pytest

from riskbands import RiskBands
from tests.test_missing_values_current_behavior import (
    fit_categorical_missing_binner,
    make_categorical_missing_frame,
)


def make_numeric_event_rate_frame(*, missing_events=20, missing_non_events=20):
    score = []
    target = []
    for value, event_rate in [(-5.0, 0.05), (-3.0, 0.20), (0.0, 0.50), (3.0, 0.80), (5.0, 0.95)]:
        n = 40
        events = int(n * event_rate)
        score.extend([value] * n)
        target.extend([1] * events + [0] * (n - events))
    score.extend([np.nan] * (missing_events + missing_non_events))
    target.extend([1] * missing_events + [0] * missing_non_events)
    return pd.DataFrame({"score": score, "target": target})


def make_categorical_event_rate_frame():
    rating = []
    target = []
    for category, event_rate in [("A", 0.10), ("B", 0.50), ("C", 0.90)]:
        n = 40
        events = int(n * event_rate)
        rating.extend([category] * n)
        target.extend([1] * events + [0] * (n - events))
    rating.extend([None] * 40)
    target.extend([1] * 20 + [0] * 20)
    return pd.DataFrame({"rating": rating, "target": target})


def fit_numeric_merge(df=None, **kwargs):
    df = make_numeric_event_rate_frame() if df is None else df
    binner = RiskBands(
        max_bins=5,
        min_event_rate_diff=0.0,
        missing_policy="merge",
        missing_merge_criterion="nearest_event_rate",
        **kwargs,
    )
    return binner.fit(df, y="target", column="score"), df


def selected_candidate(binner):
    selected = binner.missing_merge_candidates_.loc[binner.missing_merge_candidates_["selected"]]
    assert len(selected) == 1
    return selected.iloc[0]


def row_for_label(df, label_column, label):
    key = str(label)
    rows = df.loc[df[label_column].astype(str) == key]
    assert len(rows) == 1
    return rows.iloc[0]


def test_numeric_nearest_event_rate_merges_missing_into_expected_bin():
    binner, df = fit_numeric_merge()
    decision = binner.missing_decision_log_.iloc[0]
    candidate = selected_candidate(binner)

    transformed = binner.transform(pd.DataFrame({"score": [np.nan, -5.0, 5.0]}))

    assert decision["action"] == "missing_merged"
    assert decision["status"] == "merged"
    assert decision["merge_criterion"] == "nearest_event_rate"
    assert decision["selected_bin_label"] == candidate["candidate_bin_label"]
    assert candidate["distance_event_rate"] == pytest.approx(0.0)
    assert transformed.loc[0, "score"] == decision["selected_bin_label"]
    assert transformed.loc[0, "score"] != "Missing"
    assert "Missing" not in set(binner.bin_summary["bin"].astype(str))
    assert binner.missing_profile_.iloc[0]["bin_label"] == "Missing"
    assert int(binner.missing_profile_.iloc[0]["n_missing_fit"]) == int(df["score"].isna().sum())


def test_numeric_merge_return_woe_routes_missing_to_selected_bin_woe():
    binner, _ = fit_numeric_merge()
    decision = binner.missing_decision_log_.iloc[0]
    selected_label = decision["selected_bin_label"]
    profile_row = row_for_label(binner.fit_profile_, "bin_label", selected_label)

    transformed = binner.transform(pd.DataFrame({"score": [np.nan, -5.0, 5.0]}), return_woe=True)

    assert pd.api.types.is_numeric_dtype(transformed["score"])
    assert not isinstance(transformed.loc[0, "score"], str)
    assert transformed.loc[0, "score"] == pytest.approx(profile_row["woe"])


def test_optuna_merge_preserves_child_missing_audit_artifacts():
    df = make_numeric_event_rate_frame(missing_events=10, missing_non_events=10)
    binner = RiskBands(
        max_bins=5,
        min_event_rate_diff=0.0,
        use_optuna=True,
        missing_policy="merge",
        missing_merge_criterion="nearest_event_rate",
        strategy_kwargs={"n_trials": 2, "sampler_seed": 123},
    ).fit(df, y="target", column="score")
    child = binner._per_feature_binners["score"]
    decision = binner.missing_decision_log_.iloc[0]
    child_decision = child.missing_decision_log_.iloc[0]
    selected_label = decision["selected_bin_label"]
    profile_row = row_for_label(binner.missing_profile_, "bin_label", "Missing")

    transformed = binner.transform(pd.DataFrame({"score": [np.nan, -5.0]}))
    transformed_woe = binner.transform(pd.DataFrame({"score": [np.nan, -5.0]}), return_woe=True)
    fit_profile_row = row_for_label(binner.fit_profile_, "bin_label", selected_label)
    summary_row = row_for_label(binner.bin_summary, "bin", selected_label)

    assert decision["action"] == "missing_merged"
    assert selected_label == child_decision["selected_bin_label"]
    assert profile_row["merged_into_bin_label"] == selected_label
    assert int(profile_row["n_missing_fit"]) == int(df["score"].isna().sum())
    assert binner.missing_merge_map_["score"] == selected_label
    assert not binner.missing_merge_candidates_.empty
    assert transformed.loc[0, "score"] == selected_label
    assert transformed.loc[0, "score"] != "Missing"
    assert pd.api.types.is_numeric_dtype(transformed_woe["score"])
    assert not isinstance(transformed_woe.loc[0, "score"], str)
    assert transformed_woe.loc[0, "score"] == pytest.approx(fit_profile_row["woe"])
    assert "Missing" not in set(binner.bin_summary["bin"].astype(str))
    assert summary_row["count"] == pytest.approx(fit_profile_row["n"])
    assert summary_row["event_rate"] == pytest.approx(fit_profile_row["event_rate"])


def test_bin_summary_selected_bin_matches_fit_profile_after_missing_merge():
    binner, _ = fit_numeric_merge()
    decision = binner.missing_decision_log_.iloc[0]
    selected_label = decision["selected_bin_label"]
    metrics_before = decision["metrics_before"]
    summary_row = row_for_label(binner.bin_summary, "bin", selected_label)
    profile_row = row_for_label(binner.fit_profile_, "bin_label", selected_label)
    expected_n = metrics_before["selected_bin"]["n"] + metrics_before["missing"]["n"]
    expected_events = metrics_before["selected_bin"]["events"] + metrics_before["missing"]["events"]
    expected_non_events = (
        metrics_before["selected_bin"]["non_events"]
        + metrics_before["missing"]["non_events"]
    )

    assert "Missing" not in set(binner.bin_summary["bin"].astype(str))
    assert summary_row["count"] == pytest.approx(expected_n)
    assert summary_row["event"] == pytest.approx(expected_events)
    assert summary_row["non_event"] == pytest.approx(expected_non_events)
    assert summary_row["event_rate"] == pytest.approx(expected_events / expected_n)
    assert summary_row["count"] == pytest.approx(profile_row["n"])
    assert summary_row["event"] == pytest.approx(profile_row["events"])
    assert summary_row["non_event"] == pytest.approx(profile_row["non_events"])
    assert summary_row["event_rate"] == pytest.approx(profile_row["event_rate"])
    if "share" in binner.bin_summary.columns:
        assert summary_row["share"] == pytest.approx(profile_row["share"])
    if "woe" in binner.bin_summary.columns:
        assert summary_row["woe"] == pytest.approx(profile_row["woe"])
    if "iv_component" in binner.bin_summary.columns:
        assert summary_row["iv_component"] == pytest.approx(profile_row["iv_component"])


def test_categorical_nearest_event_rate_merges_missing_into_expected_bin():
    df = make_categorical_event_rate_frame()
    binner = RiskBands(
        max_bins=3,
        min_event_rate_diff=0.0,
        force_categorical=["rating"],
        missing_policy="merge",
        missing_merge_criterion="nearest_event_rate",
    ).fit(df, y="target", column="rating")
    decision = binner.missing_decision_log_.iloc[0]
    candidate = selected_candidate(binner)

    transformed = binner.transform(pd.DataFrame({"rating": [None, "A", "Z"]}))

    assert decision["action"] == "missing_merged"
    assert decision["selected_bin_label"] == candidate["candidate_bin_label"]
    assert candidate["candidate_event_rate"] == pytest.approx(0.5)
    assert transformed.loc[0, "rating"] == decision["selected_bin_label"]
    assert transformed.loc[0, "rating"] != "Missing"
    assert binner.missing_profile_.iloc[0]["bin_label"] == "Missing"


def test_nearest_event_rate_tie_break_prefers_larger_candidate_n():
    rating = []
    target = []
    for category, n, events in [("A", 40, 10), ("B", 80, 60), ("C", 40, 4)]:
        rating.extend([category] * n)
        target.extend([1] * events + [0] * (n - events))
    rating.extend([None] * 40)
    target.extend([1] * 20 + [0] * 20)
    df = pd.DataFrame({"rating": rating, "target": target})

    binner = RiskBands(
        max_bins=3,
        min_event_rate_diff=0.0,
        force_categorical=["rating"],
        missing_policy="merge",
        missing_merge_criterion="nearest_event_rate",
    ).fit(df, y="target", column="rating")

    decision = binner.missing_decision_log_.iloc[0]
    candidates = binner.missing_merge_candidates_
    min_distance = candidates["distance_event_rate"].min()
    tied = candidates.loc[np.isclose(candidates["distance_event_rate"], min_distance)]
    candidate = selected_candidate(binner)

    assert bool(decision["tie_detected"]) is True
    assert len(tied) >= 2
    assert candidate["candidate_n"] == tied["candidate_n"].max()


@pytest.mark.parametrize(
    ("missing_events", "missing_non_events", "expected_rate"),
    [
        (0, 40, 0.0),
        (40, 0, 1.0),
    ],
)
def test_nearest_event_rate_handles_zero_or_all_missing_events(
    missing_events,
    missing_non_events,
    expected_rate,
):
    df = make_numeric_event_rate_frame(
        missing_events=missing_events,
        missing_non_events=missing_non_events,
    )
    binner, _ = fit_numeric_merge(df)
    candidate = selected_candidate(binner)

    assert binner.missing_profile_.iloc[0]["event_rate_missing_fit"] == pytest.approx(expected_rate)
    assert candidate["missing_event_rate"] == pytest.approx(expected_rate)
    assert binner.missing_decision_log_.iloc[0]["action"] == "missing_merged"


def test_no_missing_in_fit_transform_missing_uses_separate_bin_fallback():
    df = pd.DataFrame({"score": [-5.0, -4.0, 0.0, 3.0, 5.0] * 10, "target": [0, 0, 1, 1, 1] * 10})
    binner = RiskBands(
        max_bins=3,
        min_event_rate_diff=0.0,
        missing_policy="merge",
        missing_merge_criterion="nearest_event_rate",
        missing_merge_fallback="separate_bin",
    ).fit(df, y="target", column="score")

    transformed = binner.transform(pd.DataFrame({"score": [np.nan, -5.0]}))

    assert binner.missing_merge_map_ == {}
    assert binner.missing_decision_log_.iloc[0]["action"] == "no_missing_detected"
    assert transformed.loc[0, "score"] == "Missing"


def test_no_missing_in_fit_transform_missing_raise_fallback_errors():
    df = pd.DataFrame({"score": [-5.0, -4.0, 0.0, 3.0, 5.0] * 10, "target": [0, 0, 1, 1, 1] * 10})
    binner = RiskBands(
        max_bins=3,
        min_event_rate_diff=0.0,
        missing_policy="merge",
        missing_merge_criterion="nearest_event_rate",
        missing_merge_fallback="raise",
    ).fit(df, y="target", column="score")

    with pytest.raises(ValueError, match="no missing merge decision was learned"):
        binner.transform(pd.DataFrame({"score": [np.nan, -5.0]}))


def test_standard_and_separate_bin_current_behaviors_remain_distinct():
    standard, df = fit_categorical_missing_binner()
    separate = RiskBands(
        max_bins=4,
        min_event_rate_diff=0.0,
        force_categorical=["grade"],
        missing_policy="separate_bin",
    ).fit(make_categorical_missing_frame(), y="target", column="grade")

    standard_transformed = standard.transform(df[["grade"]])
    separate_transformed = separate.transform(df[["grade"]])

    assert standard.fit_profile_.loc[standard.fit_profile_["is_missing_bin"]].empty
    assert set(separate_transformed.loc[df["grade"].isna(), "grade"]) == {"Missing"}
    assert set(standard_transformed.loc[df["grade"].isna(), "grade"]) != {"Missing"}
