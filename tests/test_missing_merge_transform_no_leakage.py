import numpy as np
import pandas as pd
import pytest

from riskbands import RiskBands
from tests.test_missing_merge_nearest_event_rate_pandas import fit_numeric_merge, row_for_label
from tests.test_missing_merge_nearest_woe_pandas import fit_numeric_woe_merge


def make_no_missing_numeric_frame():
    return pd.DataFrame(
        {
            "score": [-5.0, -4.0, -3.0, 0.0, 3.0, 4.0, 5.0] * 8,
            "target": [0, 0, 0, 1, 1, 1, 1] * 8,
        }
    )


def test_transform_target_values_do_not_change_learned_missing_destination():
    binner, _ = fit_numeric_merge()
    learned_destination = binner.missing_decision_log_.iloc[0]["selected_bin_label"]
    decision_before = binner.missing_decision_log_.copy(deep=True)
    app = pd.DataFrame(
        {
            "score": [np.nan, np.nan, -5.0, 5.0],
            "target": [1, 1, 1, 1],
        }
    )

    transformed = binner.transform(app, column="score", validate=True)

    assert set(transformed.loc[[0, 1], "score"]) == {learned_destination}
    assert binner.missing_decision_log_.equals(decision_before)
    assert binner.missing_transform_fallback_log_.iloc[0]["action"] == "missing_routed_to_learned_merge"
    assert bool(binner.missing_transform_fallback_log_.iloc[0]["training_decision_used"]) is True


def test_transform_without_target_uses_learned_missing_destination():
    binner, _ = fit_numeric_merge()
    learned_destination = binner.missing_decision_log_.iloc[0]["selected_bin_label"]

    transformed = binner.transform(pd.DataFrame({"score": [np.nan, -5.0, 5.0]}))

    assert transformed.loc[0, "score"] == learned_destination


def test_nearest_woe_transform_without_target_uses_learned_missing_destination():
    binner, _ = fit_numeric_woe_merge()
    learned_destination = binner.missing_decision_log_.iloc[0]["selected_bin_label"]

    transformed = binner.transform(pd.DataFrame({"score": [np.nan, -5.0, 5.0]}))

    assert transformed.loc[0, "score"] == learned_destination


def test_nearest_woe_return_woe_uses_final_selected_bin_value():
    binner, _ = fit_numeric_woe_merge()
    learned_destination = binner.missing_decision_log_.iloc[0]["selected_bin_label"]
    profile_row = row_for_label(binner.fit_profile_, "bin_label", learned_destination)

    transformed = binner.transform(pd.DataFrame({"score": [np.nan, -5.0]}), return_woe=True)

    assert pd.api.types.is_numeric_dtype(transformed["score"])
    assert transformed.loc[0, "score"] == pytest.approx(profile_row["woe"])


def test_repeated_transform_is_deterministic():
    binner, _ = fit_numeric_merge()
    app = pd.DataFrame({"score": [np.nan, -5.0, 0.0, 5.0, np.nan]})

    first = binner.transform(app)
    second = binner.transform(app)

    assert first.equals(second)


def test_transform_missing_not_seen_in_fit_uses_separate_bin_fallback_and_logs_it():
    df = make_no_missing_numeric_frame()
    binner = RiskBands(
        max_bins=4,
        min_event_rate_diff=0.0,
        missing_policy="merge",
        missing_merge_criterion="nearest_event_rate",
        missing_merge_fallback="separate_bin",
    ).fit(df, y="target", column="score")

    transformed = binner.transform(pd.DataFrame({"score": [np.nan, -5.0]}))
    log = binner.missing_transform_fallback_log_.iloc[0]

    assert transformed.loc[0, "score"] == "Missing"
    assert log["action"] == "missing_transform_fallback_separate_bin"
    assert bool(log["fallback_used"]) is True
    assert bool(log["training_decision_used"]) is False


def test_transform_missing_not_seen_in_fit_return_woe_errors_for_separate_fallback():
    df = make_no_missing_numeric_frame()
    binner = RiskBands(
        max_bins=4,
        min_event_rate_diff=0.0,
        missing_policy="merge",
        missing_merge_criterion="nearest_event_rate",
        missing_merge_fallback="separate_bin",
    ).fit(df, y="target", column="score")

    with pytest.raises(ValueError, match="fallback 'separate_bin' has no fitted WoE"):
        binner.transform(pd.DataFrame({"score": [np.nan, -5.0]}), return_woe=True)

    log = binner.missing_transform_fallback_log_.iloc[0]
    assert log["action"] == "missing_transform_fallback_separate_bin"
    assert bool(log["fallback_used"]) is True
    assert bool(log["training_decision_used"]) is False


def test_transform_missing_not_seen_in_fit_raise_fallback_errors_and_logs_it():
    df = make_no_missing_numeric_frame()
    binner = RiskBands(
        max_bins=4,
        min_event_rate_diff=0.0,
        missing_policy="merge",
        missing_merge_criterion="nearest_event_rate",
        missing_merge_fallback="raise",
    ).fit(df, y="target", column="score")

    with pytest.raises(ValueError, match="no missing merge decision was learned"):
        binner.transform(pd.DataFrame({"score": [np.nan, -5.0]}))

    log = binner.missing_transform_fallback_log_.iloc[0]
    assert log["action"] == "missing_transform_fallback_raise"
    assert bool(log["fallback_used"]) is True


def test_transform_application_distribution_cannot_retarget_missing_merge():
    binner, _ = fit_numeric_merge()
    learned_destination = binner.missing_decision_log_.iloc[0]["selected_bin_label"]
    adversarial_app = pd.DataFrame(
        {
            "score": [np.nan] * 20 + [-5.0] * 20 + [5.0] * 20,
            "target": [0] * 20 + [0] * 20 + [1] * 20,
        }
    )

    transformed = binner.transform(adversarial_app, column="score", validate=True)

    assert set(transformed.loc[adversarial_app["score"].isna(), "score"]) == {learned_destination}
    assert binner.missing_decision_log_.iloc[0]["selected_bin_label"] == learned_destination


def test_nearest_woe_application_distribution_cannot_retarget_missing_merge():
    binner, _ = fit_numeric_woe_merge()
    learned_destination = binner.missing_decision_log_.iloc[0]["selected_bin_label"]
    decision_before = binner.missing_decision_log_.copy(deep=True)
    adversarial_app = pd.DataFrame(
        {
            "score": [np.nan] * 20 + [-5.0] * 20 + [5.0] * 20,
            "target": [1] * 20 + [0] * 20 + [1] * 20,
        }
    )

    transformed = binner.transform(adversarial_app, column="score", validate=True)

    assert set(transformed.loc[adversarial_app["score"].isna(), "score"]) == {learned_destination}
    assert binner.missing_decision_log_.equals(decision_before)
