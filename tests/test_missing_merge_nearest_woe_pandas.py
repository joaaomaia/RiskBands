import numpy as np
import pandas as pd
import pytest

from riskbands import RiskBands
from tests.test_missing_merge_nearest_event_rate_pandas import (
    make_numeric_event_rate_frame,
    row_for_label,
)


def make_categorical_woe_difference_frame():
    rating = []
    target = []
    for category, n, events in [
        ("A", 100, 10),
        ("B", 100, 35),
        ("C", 100, 80),
    ]:
        rating.extend([category] * n)
        target.extend([1] * events + [0] * (n - events))
    rating.extend([None] * 100)
    target.extend([1] * 20 + [0] * 80)
    return pd.DataFrame({"rating": rating, "target": target})


def fit_numeric_woe_merge(df=None, **kwargs):
    df = make_numeric_event_rate_frame() if df is None else df
    binner = RiskBands(
        max_bins=5,
        min_event_rate_diff=0.0,
        missing_policy="merge",
        missing_merge_criterion="nearest_woe",
        **kwargs,
    )
    return binner.fit(df, y="target", column="score"), df


def fit_categorical_woe_merge(df=None, **kwargs):
    df = make_categorical_woe_difference_frame() if df is None else df
    binner = RiskBands(
        max_bins=3,
        min_event_rate_diff=0.0,
        force_categorical=["rating"],
        missing_policy="merge",
        missing_merge_criterion="nearest_woe",
        **kwargs,
    )
    return binner.fit(df, y="target", column="rating"), df


def selected_woe_candidate(binner):
    selected = binner.missing_merge_candidates_.loc[binner.missing_merge_candidates_["selected"]]
    assert len(selected) == 1
    return selected.iloc[0]


def assert_selected_by_min_woe_distance(binner):
    candidates = binner.missing_merge_candidates_
    selected = selected_woe_candidate(binner)
    decision = binner.missing_decision_log_.iloc[0]

    assert decision["missing_merge_criterion"] == "nearest_woe"
    assert decision["distance_metric"] == "abs_woe_diff"
    assert selected["distance_woe"] == pytest.approx(candidates["distance_woe"].min())
    assert decision["distance"] == pytest.approx(selected["distance_woe"])
    assert decision["distance_woe"] == pytest.approx(selected["distance_woe"])
    assert decision["selected_bin_woe"] == pytest.approx(selected["candidate_woe"])
    assert decision["missing_woe"] == pytest.approx(selected["missing_woe"])


def test_numeric_nearest_woe_merges_missing_into_expected_bin():
    binner, _ = fit_numeric_woe_merge()
    decision = binner.missing_decision_log_.iloc[0]
    selected = selected_woe_candidate(binner)

    transformed = binner.transform(pd.DataFrame({"score": [np.nan, -5.0, 5.0]}))

    assert decision["action"] == "missing_merged"
    assert decision["status"] == "merged"
    assert_selected_by_min_woe_distance(binner)
    assert transformed.loc[0, "score"] == selected["candidate_bin_label"]
    assert transformed.loc[0, "score"] != "Missing"
    assert "Missing" not in set(binner.bin_summary["bin"].astype(str))
    assert binner.missing_profile_.iloc[0]["woe_missing_fit"] == pytest.approx(selected["missing_woe"])


def test_categorical_nearest_woe_merges_missing_into_expected_bin():
    binner, _ = fit_categorical_woe_merge()
    decision = binner.missing_decision_log_.iloc[0]
    selected = selected_woe_candidate(binner)

    transformed = binner.transform(pd.DataFrame({"rating": [None, "A", "Z"]}))

    assert decision["action"] == "missing_merged"
    assert_selected_by_min_woe_distance(binner)
    assert transformed.loc[0, "rating"] == selected["candidate_bin_label"]
    assert transformed.loc[0, "rating"] != "Missing"


def test_nearest_event_rate_and_nearest_woe_can_choose_different_bins():
    df = make_categorical_woe_difference_frame()
    event_rate_binner = RiskBands(
        max_bins=3,
        min_event_rate_diff=0.0,
        force_categorical=["rating"],
        missing_policy="merge",
        missing_merge_criterion="nearest_event_rate",
    ).fit(df, y="target", column="rating")
    woe_binner = RiskBands(
        max_bins=3,
        min_event_rate_diff=0.0,
        force_categorical=["rating"],
        missing_policy="merge",
        missing_merge_criterion="nearest_woe",
    ).fit(df, y="target", column="rating")

    event_rate_decision = event_rate_binner.missing_decision_log_.iloc[0]
    woe_decision = woe_binner.missing_decision_log_.iloc[0]

    assert event_rate_decision["selected_bin_label"] != woe_decision["selected_bin_label"]
    assert event_rate_decision["distance_metric"] == "abs_event_rate_diff"
    assert woe_decision["distance_metric"] == "abs_woe_diff"


def test_numeric_merge_return_woe_routes_missing_to_selected_bin_woe():
    binner, _ = fit_numeric_woe_merge()
    decision = binner.missing_decision_log_.iloc[0]
    selected_label = decision["selected_bin_label"]
    profile_row = row_for_label(binner.fit_profile_, "bin_label", selected_label)

    transformed = binner.transform(pd.DataFrame({"score": [np.nan, -5.0, 5.0]}), return_woe=True)

    assert pd.api.types.is_numeric_dtype(transformed["score"])
    assert not isinstance(transformed.loc[0, "score"], str)
    assert transformed.loc[0, "score"] == pytest.approx(profile_row["woe"])


def _manual_woe_profile(*, missing_woe=0.0, candidate_woes=(1.0, -1.0)):
    return pd.DataFrame(
        [
            {
                "variable": "score",
                "bin_id": "missing",
                "bin_label": "Missing",
                "bin_order": 2,
                "n": 10,
                "events": 5,
                "non_events": 5,
                "event_rate": 0.5,
                "share": 0.25,
                "woe": missing_woe,
                "is_missing_bin": True,
                "is_special_bin": False,
                "is_regular_bin": False,
            },
            {
                "variable": "score",
                "bin_id": "A",
                "bin_label": "A",
                "bin_order": 0,
                "n": 10,
                "events": 2,
                "non_events": 8,
                "event_rate": 0.2,
                "share": 0.25,
                "woe": candidate_woes[0],
                "is_missing_bin": False,
                "is_special_bin": False,
                "is_regular_bin": True,
            },
            {
                "variable": "score",
                "bin_id": "B",
                "bin_label": "B",
                "bin_order": 1,
                "n": 20,
                "events": 16,
                "non_events": 4,
                "event_rate": 0.8,
                "share": 0.50,
                "woe": candidate_woes[1],
                "is_missing_bin": False,
                "is_special_bin": False,
                "is_regular_bin": True,
            },
        ]
    )


def _build_manual_woe_audit(pre_profile, *, fallback="separate_bin"):
    binner = RiskBands(
        missing_policy="merge",
        missing_merge_criterion="nearest_woe",
        missing_merge_fallback=fallback,
    )
    binner.feature_names_in_ = ["score"]
    X = pd.DataFrame({"score": [np.nan] * 10 + [0.0] * 10 + [1.0] * 20})
    y = pd.Series([0, 1] * 20, name="target")
    binner._build_missing_merge_audit_from_fit(X, y, pre_profile, backend="pandas")
    return binner


def test_nearest_woe_tie_break_prefers_larger_candidate_n():
    binner = _build_manual_woe_audit(_manual_woe_profile())
    decision = binner.missing_decision_log_.iloc[0]
    selected = selected_woe_candidate(binner)

    assert bool(decision["tie_detected"]) is True
    assert bool(decision["tie_break_applied"]) is True
    assert selected["candidate_bin_label"] == "B"
    assert selected["candidate_n"] == 20
    assert "candidate_n desc" in decision["tie_break_rule"]


def test_nearest_woe_missing_non_finite_uses_separate_fallback():
    binner = _build_manual_woe_audit(_manual_woe_profile(missing_woe=np.nan))
    decision = binner.missing_decision_log_.iloc[0]

    assert decision["action"] == "missing_kept_separate"
    assert decision["status"] == "kept_separate"
    assert bool(decision["fallback_used"]) is True
    assert decision["reason"] == "missing_woe_not_finite"


def test_nearest_woe_no_finite_candidate_uses_separate_fallback():
    binner = _build_manual_woe_audit(_manual_woe_profile(candidate_woes=(np.nan, np.nan)))
    decision = binner.missing_decision_log_.iloc[0]

    assert decision["action"] == "missing_kept_separate"
    assert decision["status"] == "kept_separate"
    assert bool(decision["fallback_used"]) is True
    assert decision["reason"] == "no_finite_candidate_woe"


def test_nearest_woe_no_finite_candidate_raise_fallback_errors():
    with pytest.raises(ValueError, match="nearest_woe candidates"):
        _build_manual_woe_audit(
            _manual_woe_profile(candidate_woes=(np.nan, np.nan)),
            fallback="raise",
        )


def test_standard_separate_bin_and_forbid_stay_intact_with_nearest_woe_available():
    standard = RiskBands(missing_policy="standard", min_event_rate_diff=0.0).fit(
        pd.DataFrame({"score": [1.0, 2.0, np.nan, 4.0], "target": [0, 1, 0, 1]}),
        y="target",
        column="score",
    )
    separate = RiskBands(missing_policy="separate_bin", min_event_rate_diff=0.0).fit(
        pd.DataFrame({"score": [1.0, 2.0, np.nan, 4.0], "target": [0, 1, 0, 1]}),
        y="target",
        column="score",
    )
    forbid = RiskBands(missing_policy="forbid", min_event_rate_diff=0.0).fit(
        pd.DataFrame({"score": [1.0, 2.0, 3.0, 4.0], "target": [0, 1, 0, 1]}),
        y="target",
        column="score",
    )

    assert standard.missing_policy_ == "standard"
    assert separate.missing_policy_ == "separate_bin"
    assert forbid.missing_policy_ == "forbid"
    assert standard.missing_merge_criterion_ is None
    assert separate.missing_merge_criterion_ is None
    assert forbid.missing_merge_criterion_ is None
