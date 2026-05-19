import json

import numpy as np
import pandas as pd
import pytest

from riskbands import RiskBands


def _block(value, n, events):
    return [value] * n, [1] * events + [0] * (n - events)


def make_numeric_frame(*, missing_events=12, missing_non_events=12, regular_specs=None):
    regular_specs = regular_specs or [
        (-5.0, 40, 4),
        (-1.0, 40, 16),
        (1.0, 40, 24),
        (5.0, 40, 36),
    ]
    score = []
    target = []
    for value, n, events in regular_specs:
        values, outcomes = _block(value, n, events)
        score.extend(values)
        target.extend(outcomes)
    score.extend([np.nan] * (missing_events + missing_non_events))
    target.extend([1] * missing_events + [0] * missing_non_events)
    return pd.DataFrame({"score": score, "target": target})


def fit_numeric_merge(df, *, criterion="nearest_event_rate", **kwargs):
    binner = RiskBands(
        max_bins=5,
        min_event_rate_diff=0.0,
        missing_policy="merge",
        missing_merge_criterion=criterion,
        **kwargs,
    )
    return binner.fit(df, y="target", column="score")


def selected_candidate(binner):
    selected = binner.missing_merge_candidates_.loc[binner.missing_merge_candidates_["selected"]]
    assert len(selected) == 1
    return selected.iloc[0]


def row_for_label(df, label_column, label):
    rows = df.loc[df[label_column].map(str) == str(label)]
    assert len(rows) == 1
    return rows.iloc[0]


def make_manual_profile(*, regular_rows):
    rows = [
        {
            "variable": "score",
            "bin_id": "missing",
            "bin_label": "Missing",
            "bin_order": 99,
            "n": 20,
            "events": 10,
            "non_events": 10,
            "event_rate": 0.5,
            "share": 0.25,
            "woe": 0.0,
            "is_missing_bin": True,
            "is_special_bin": False,
            "is_regular_bin": False,
        }
    ]
    rows.extend(regular_rows)
    return pd.DataFrame(rows)


def regular_profile_row(label, *, n, events, event_rate=None, woe=0.0, order=0):
    event_rate = events / n if event_rate is None else event_rate
    return {
        "variable": "score",
        "bin_id": label,
        "bin_label": label,
        "bin_order": order,
        "n": n,
        "events": events,
        "non_events": n - events,
        "event_rate": event_rate,
        "share": n / 80,
        "woe": woe,
        "is_missing_bin": False,
        "is_special_bin": False,
        "is_regular_bin": True,
    }


def build_manual_audit(profile, *, criterion="nearest_event_rate", fallback="separate_bin"):
    binner = RiskBands(
        missing_policy="merge",
        missing_merge_criterion=criterion,
        missing_merge_fallback=fallback,
    )
    binner.feature_names_in_ = ["score"]
    total_regular = int(profile.loc[~profile["is_missing_bin"], "n"].sum())
    X = pd.DataFrame({"score": [np.nan] * 20 + [0.0] * total_regular})
    y = pd.Series([0, 1] * ((len(X) + 1) // 2), name="target").iloc[: len(X)]
    binner._build_missing_merge_audit_from_fit(X, y, profile, backend="pandas")
    return binner


@pytest.mark.parametrize(
    ("missing_events", "missing_non_events", "expected_n"),
    [
        (1, 0, 1),
        (120, 40, 160),
    ],
)
def test_nearest_event_rate_handles_very_rare_and_very_frequent_missing(
    missing_events,
    missing_non_events,
    expected_n,
):
    df = make_numeric_frame(
        missing_events=missing_events,
        missing_non_events=missing_non_events,
    )
    binner = fit_numeric_merge(df)

    decision = binner.missing_decision_log_.iloc[0]
    profile = binner.missing_profile_.iloc[0]

    assert decision["action"] == "missing_merged"
    assert decision["candidate_count"] >= 1
    assert int(profile["n_missing_fit"]) == expected_n
    assert profile["merge_status"] == "merged"


@pytest.mark.parametrize(
    ("missing_events", "missing_non_events", "expected_rate"),
    [
        (0, 24, 0.0),
        (24, 0, 1.0),
    ],
)
def test_zero_or_all_event_missing_groups_still_route_and_return_woe(
    missing_events,
    missing_non_events,
    expected_rate,
):
    df = make_numeric_frame(
        missing_events=missing_events,
        missing_non_events=missing_non_events,
    )
    binner = fit_numeric_merge(df)

    transformed_woe = binner.transform(pd.DataFrame({"score": [np.nan, -5.0]}), return_woe=True)

    assert binner.missing_profile_.iloc[0]["event_rate_missing_fit"] == pytest.approx(expected_rate)
    assert binner.missing_decision_log_.iloc[0]["action"] == "missing_merged"
    assert pd.api.types.is_numeric_dtype(transformed_woe["score"])
    assert np.isfinite(float(transformed_woe.loc[0, "score"]))


def test_missing_event_rate_equal_to_candidate_records_zero_distance():
    df = make_numeric_frame(
        missing_events=12,
        missing_non_events=12,
        regular_specs=[
            (-5.0, 40, 4),
            (-1.0, 40, 20),
            (1.0, 40, 28),
            (5.0, 40, 36),
        ],
    )
    binner = fit_numeric_merge(df)
    candidate = selected_candidate(binner)

    assert candidate["missing_event_rate"] == pytest.approx(candidate["candidate_event_rate"])
    assert candidate["distance_event_rate"] == pytest.approx(0.0)
    assert binner.missing_decision_log_.iloc[0]["distance"] == pytest.approx(0.0)


def test_nearest_event_rate_tie_break_is_deterministic():
    profile = make_manual_profile(
        regular_rows=[
            regular_profile_row("A", n=20, events=8, event_rate=0.4, woe=-0.5, order=0),
            regular_profile_row("B", n=40, events=24, event_rate=0.6, woe=0.5, order=1),
        ]
    )
    binner = build_manual_audit(profile)
    decision = binner.missing_decision_log_.iloc[0]
    candidate = selected_candidate(binner)

    assert bool(decision["tie_detected"]) is True
    assert bool(decision["tie_break_applied"]) is True
    assert candidate["candidate_bin_label"] == "B"
    assert candidate["candidate_n"] == 40
    assert "candidate_n desc" in decision["tie_break_rule"]


def test_nearest_woe_tie_break_is_deterministic():
    profile = make_manual_profile(
        regular_rows=[
            regular_profile_row("A", n=20, events=8, event_rate=0.4, woe=-1.0, order=0),
            regular_profile_row("B", n=40, events=24, event_rate=0.6, woe=1.0, order=1),
        ]
    )
    binner = build_manual_audit(profile, criterion="nearest_woe")
    decision = binner.missing_decision_log_.iloc[0]
    candidate = selected_candidate(binner)

    assert bool(decision["tie_detected"]) is True
    assert candidate["candidate_bin_label"] == "B"
    assert candidate["distance_woe"] == pytest.approx(1.0)


def test_single_candidate_bin_is_selected_without_tie():
    profile = make_manual_profile(
        regular_rows=[
            regular_profile_row("Only regular bin", n=40, events=20, event_rate=0.5, woe=0.0)
        ]
    )
    binner = build_manual_audit(profile)
    decision = binner.missing_decision_log_.iloc[0]
    candidate = selected_candidate(binner)

    assert decision["action"] == "missing_merged"
    assert decision["candidate_count"] == 1
    assert bool(decision["tie_detected"]) is False
    assert candidate["candidate_bin_label"] == "Only regular bin"


def test_no_regular_candidate_uses_separate_bin_fallback():
    profile = make_manual_profile(regular_rows=[])
    binner = build_manual_audit(profile, fallback="separate_bin")
    decision = binner.missing_decision_log_.iloc[0]

    assert decision["action"] == "missing_kept_separate"
    assert decision["status"] == "kept_separate"
    assert decision["reason"] == "no_regular_candidate_bins"
    assert bool(decision["fallback_used"]) is True
    assert binner.missing_merge_candidates_.empty
    assert binner.missing_merge_map_ == {}


def test_no_regular_candidate_raise_fallback_errors():
    profile = make_manual_profile(regular_rows=[])

    with pytest.raises(ValueError, match="no regular candidate bin"):
        build_manual_audit(profile, fallback="raise")


def test_categorical_missing_with_rare_category_keeps_merge_auditable():
    rating = []
    target = []
    for category, n, events in [
        ("A", 40, 4),
        ("B", 40, 20),
        ("C", 40, 32),
        ("Rare", 2, 1),
    ]:
        rating.extend([category] * n)
        target.extend([1] * events + [0] * (n - events))
    rating.extend([None] * 20)
    target.extend([1] * 10 + [0] * 10)
    df = pd.DataFrame({"rating": rating, "target": target})

    binner = RiskBands(
        max_bins=4,
        min_event_rate_diff=0.0,
        force_categorical=["rating"],
        missing_policy="merge",
        missing_merge_criterion="nearest_event_rate",
    ).fit(df, y="target", column="rating")
    transformed = binner.transform(pd.DataFrame({"rating": [None, "Rare"]}))

    assert binner.missing_decision_log_.iloc[0]["action"] == "missing_merged"
    assert not binner.missing_merge_candidates_.empty
    assert transformed.loc[0, "rating"] == binner.missing_decision_log_.iloc[0]["selected_bin_label"]


def test_force_numeric_missing_merge_routes_string_numeric_inputs():
    df = make_numeric_frame()
    df["score"] = df["score"].map(lambda value: None if pd.isna(value) else f"{value:.1f}")

    binner = RiskBands(
        max_bins=5,
        min_event_rate_diff=0.0,
        force_numeric=["score"],
        missing_policy="merge",
        missing_merge_criterion="nearest_event_rate",
    ).fit(df, y="target", column="score")
    transformed = binner.transform(pd.DataFrame({"score": [None, "-5.0"]}))

    assert binner.missing_decision_log_.iloc[0]["action"] == "missing_merged"
    assert transformed.loc[0, "score"] == binner.missing_decision_log_.iloc[0]["selected_bin_label"]
    assert transformed.loc[0, "score"] != "Missing"


@pytest.mark.parametrize("fallback", ["separate_bin", "raise"])
def test_transform_missing_unobserved_during_fit_uses_configured_fallback(fallback):
    df = make_numeric_frame(missing_events=0, missing_non_events=0)
    binner = fit_numeric_merge(df, missing_merge_fallback=fallback)
    transform_df = pd.DataFrame({"score": [np.nan, -5.0]})

    assert binner.missing_decision_log_.iloc[0]["action"] == "no_missing_detected"
    assert binner.missing_merge_map_ == {}
    if fallback == "separate_bin":
        transformed = binner.transform(transform_df)
        assert transformed.loc[0, "score"] == "Missing"
        assert binner.missing_transform_fallback_log_.iloc[0]["action"] == (
            "missing_transform_fallback_separate_bin"
        )
    else:
        with pytest.raises(ValueError, match="no missing merge decision was learned"):
            binner.transform(transform_df)
        assert binner.missing_transform_fallback_log_.iloc[0]["action"] == (
            "missing_transform_fallback_raise"
        )


def test_missing_merge_candidates_are_json_serializable_in_extreme_case():
    binner = fit_numeric_merge(make_numeric_frame(missing_events=24, missing_non_events=0))

    payload = binner.missing_merge_candidates_.to_dict(orient="records")

    assert payload
    json.dumps(payload)


def test_bin_summary_and_fit_profile_remain_consistent_after_merge():
    binner = fit_numeric_merge(make_numeric_frame())
    selected_label = binner.missing_decision_log_.iloc[0]["selected_bin_label"]
    summary_row = row_for_label(binner.bin_summary, "bin", selected_label)
    profile_row = row_for_label(binner.fit_profile_, "bin_label", selected_label)

    assert "Missing" not in set(binner.bin_summary["bin"].astype(str))
    assert summary_row["count"] == pytest.approx(profile_row["n"])
    assert summary_row["event"] == pytest.approx(profile_row["events"])
    assert summary_row["non_event"] == pytest.approx(profile_row["non_events"])
    assert summary_row["event_rate"] == pytest.approx(profile_row["event_rate"])
    assert summary_row["woe"] == pytest.approx(profile_row["woe"])
    assert summary_row["iv_component"] == pytest.approx(profile_row["iv_component"])
