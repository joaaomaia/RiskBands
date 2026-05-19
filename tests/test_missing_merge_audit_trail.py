import json

import numpy as np
import pandas as pd

from riskbands import RiskBands
from tests.test_missing_merge_nearest_event_rate_pandas import fit_numeric_merge, selected_candidate


def test_missing_merge_decision_log_contains_complete_decision():
    binner, _ = fit_numeric_merge()
    row = binner.missing_decision_log_.iloc[0]
    candidate = selected_candidate(binner)

    assert row["variable"] == "score"
    assert row["policy_requested"] == "merge"
    assert row["effective_policy"] == "merge"
    assert row["missing_merge_criterion"] == "nearest_event_rate"
    assert row["missing_merge_fallback"] == "separate_bin"
    assert bool(row["missing_detected"]) is True
    assert row["n_missing_fit"] > 0
    assert row["event_rate_missing_fit"] == candidate["missing_event_rate"]
    assert row["action"] == "missing_merged"
    assert row["selected_bin_label"] == candidate["candidate_bin_label"]
    assert row["selected_bin_order"] == candidate["candidate_bin_order"]
    assert row["selected_bin_event_rate"] == candidate["candidate_event_rate"]
    assert row["distance"] == candidate["distance_event_rate"]
    assert row["distance_value"] == candidate["distance_event_rate"]
    assert bool(row["training_only"]) is True
    assert bool(row["fallback_used"]) is False
    assert "training data" in row["notes"]


def test_missing_merge_candidates_are_registered_and_mark_selected_bin():
    binner, _ = fit_numeric_merge()
    candidates = binner.missing_merge_candidates_

    assert not candidates.empty
    assert candidates["selected"].sum() == 1
    assert set(
        [
            "candidate_bin_label",
            "candidate_bin_order",
            "candidate_event_rate",
            "missing_event_rate",
            "distance_event_rate",
        ]
    ).issubset(candidates.columns)
    assert bool(candidates.sort_values("candidate_rank").iloc[0]["selected"]) is True


def test_missing_profile_preserves_original_missing_after_merge():
    binner, _ = fit_numeric_merge()
    profile = binner.missing_profile_.iloc[0]
    decision = binner.missing_decision_log_.iloc[0]

    assert bool(profile["is_missing_bin"]) is True
    assert profile["bin_label"] == "Missing"
    assert profile["merge_criterion"] == "nearest_event_rate"
    assert profile["merge_status"] == "merged"
    assert profile["merged_into_bin_label"] == decision["selected_bin_label"]
    assert profile["merge_distance"] == decision["distance"]


def test_missing_merge_decision_log_records_candidate_bins_as_json_serializable_payload():
    binner, _ = fit_numeric_merge()
    records = binner.missing_decision_log_.to_dict("records")

    payload = json.dumps(records)
    decoded = json.loads(payload)

    assert decoded[0]["candidate_bins"]
    assert decoded[0]["candidate_bins"][0]["selected"] is True


def test_missing_merge_tie_break_is_recorded():
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
    row = binner.missing_decision_log_.iloc[0]

    assert bool(row["tie_detected"]) is True
    assert bool(row["tie_break_applied"]) is True
    assert "candidate_n desc" in row["tie_break_rule"]


def test_missing_merge_fallback_keeps_original_missing_profile_visible():
    df = pd.DataFrame({"score": [np.nan] * 6, "target": [0, 1, 0, 1, 0, 1]})
    binner = RiskBands(
        max_bins=3,
        min_event_rate_diff=0.0,
        force_categorical=["score"],
        missing_policy="merge",
        missing_merge_criterion="nearest_event_rate",
        missing_merge_fallback="separate_bin",
    ).fit(df, y="target", column="score")
    row = binner.missing_decision_log_.iloc[0]

    assert row["action"] == "missing_kept_separate"
    assert row["status"] == "kept_separate"
    assert bool(row["fallback_used"]) is True
    assert row["reason"] == "no_regular_candidate_bins"
    assert binner.missing_profile_.iloc[0]["bin_label"] == "Missing"
    assert binner.transform(pd.DataFrame({"score": [np.nan]})).iloc[0, 0] == "Missing"
