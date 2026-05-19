import json

import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from riskbands import RiskBands
from riskbands.reporting import load_bundle
from tests.test_missing_merge_hardening_edge_cases import (
    fit_numeric_merge,
    make_numeric_frame,
    row_for_label,
)


def assert_summary_matches_profile(binner):
    selected_label = binner.missing_decision_log_.iloc[0]["selected_bin_label"]
    summary_row = row_for_label(binner.bin_summary, "bin", selected_label)
    profile_row = row_for_label(binner.fit_profile_, "bin_label", selected_label)

    assert summary_row["count"] == pytest.approx(profile_row["n"])
    assert summary_row["event"] == pytest.approx(profile_row["events"])
    assert summary_row["non_event"] == pytest.approx(profile_row["non_events"])
    assert summary_row["event_rate"] == pytest.approx(profile_row["event_rate"])
    assert summary_row["woe"] == pytest.approx(profile_row["woe"])
    assert summary_row["iv_component"] == pytest.approx(profile_row["iv_component"])


@pytest.mark.parametrize("criterion", ["nearest_event_rate", "nearest_woe"])
def test_return_woe_bundle_reporting_and_candidate_serialization_for_merge(tmp_path, criterion):
    binner = fit_numeric_merge(make_numeric_frame(), criterion=criterion)
    transform_df = pd.DataFrame({"score": [np.nan, -5.0, -1.0, 5.0]})

    transformed_woe = binner.transform(transform_df, return_woe=True)
    report = binner.report()
    binner.save_report(tmp_path / f"{criterion}_report.json")
    binner.export_bundle(tmp_path / criterion)
    loaded = load_bundle(tmp_path / criterion)

    assert pd.api.types.is_numeric_dtype(transformed_woe["score"])
    assert transformed_woe["score"].notna().all()
    assert report.iloc[0]["missing_policy"] == "merge"
    assert report.iloc[0]["missing_merge_criterion"] == criterion
    assert loaded["missing_policy"] == "merge"
    assert loaded["effective_missing_policy"] == "merge"
    assert loaded["missing_merge_criterion"] == criterion
    assert loaded["missing_decision_log"][0]["action"] == "missing_merged"
    assert loaded["missing_merge_candidates"]
    assert loaded["missing_merge_map"] == binner.missing_merge_map_
    assert_summary_matches_profile(binner)
    json.dumps(binner.missing_merge_candidates_.to_dict(orient="records"))


@pytest.mark.parametrize("criterion", ["nearest_event_rate", "nearest_woe"])
def test_repeated_transform_is_deterministic_for_merge(criterion):
    binner = fit_numeric_merge(make_numeric_frame(), criterion=criterion)
    transform_df = pd.DataFrame({"score": [np.nan, -5.0, -1.0, 1.0, 5.0, np.nan]})

    first = binner.transform(transform_df)
    second = binner.transform(transform_df)
    first_woe = binner.transform(transform_df, return_woe=True)
    second_woe = binner.transform(transform_df, return_woe=True)

    assert_frame_equal(first, second)
    assert_frame_equal(first_woe, second_woe)


def test_set_params_preserves_missing_merge_contract_and_clears_criterion():
    binner = RiskBands(max_bins=3)

    binner.set_params(
        missing_policy="merge",
        missing_merge_criterion="nearest_woe",
        missing_merge_fallback="raise",
    )
    assert binner.missing_policy == "merge"
    assert binner.missing_merge_criterion == "nearest_woe"
    assert binner.missing_merge_fallback == "raise"

    binner.set_params(missing_policy="standard")
    assert binner.missing_policy == "standard"
    assert binner.missing_merge_criterion is None
    assert binner.missing_merge_criterion_ is None

    with pytest.raises(ValueError, match="required when missing_policy='merge'"):
        RiskBands().set_params(missing_policy="merge")


@pytest.mark.parametrize("criterion", ["nearest_event_rate", "nearest_woe"])
def test_optuna_path_preserves_missing_merge_audit_artifacts(criterion):
    df = make_numeric_frame(missing_events=8, missing_non_events=8)
    binner = RiskBands(
        max_bins=5,
        min_event_rate_diff=0.0,
        use_optuna=True,
        missing_policy="merge",
        missing_merge_criterion=criterion,
        strategy_kwargs={"n_trials": 2, "sampler_seed": 321},
    ).fit(df, y="target", column="score")

    decision = binner.missing_decision_log_.iloc[0]
    transformed = binner.transform(pd.DataFrame({"score": [np.nan, -5.0]}), return_woe=True)

    assert decision["action"] == "missing_merged"
    assert decision["missing_merge_criterion"] == criterion
    assert not binner.missing_profile_.empty
    assert not binner.missing_merge_candidates_.empty
    assert binner.missing_merge_map_["score"] == decision["selected_bin_label"]
    assert pd.api.types.is_numeric_dtype(transformed["score"])
    assert_summary_matches_profile(binner)


def test_standard_separate_bin_and_forbid_basic_paths_do_not_regress():
    missing_df = make_numeric_frame(missing_events=4, missing_non_events=4)
    clean_df = missing_df.dropna(subset=["score"]).copy()

    standard = RiskBands(
        max_bins=4,
        min_event_rate_diff=0.0,
        missing_policy="standard",
    ).fit(missing_df, y="target", column="score")
    separate = RiskBands(
        max_bins=4,
        min_event_rate_diff=0.0,
        missing_policy="separate_bin",
    ).fit(missing_df, y="target", column="score")
    forbid = RiskBands(
        max_bins=4,
        min_event_rate_diff=0.0,
        missing_policy="forbid",
    ).fit(clean_df, y="target", column="score")

    standard_transformed = standard.transform(missing_df[["score"]])
    separate_transformed = separate.transform(missing_df[["score"]])

    assert standard.report().iloc[0]["missing_policy"] == "standard"
    assert separate.report().iloc[0]["missing_policy"] == "separate_bin"
    assert forbid.report().iloc[0]["missing_policy"] == "forbid"
    assert "Missing" in set(separate_transformed["score"].astype(str))
    assert standard_transformed.shape[0] == len(missing_df)
    with pytest.raises(ValueError, match="missing_policy='forbid'"):
        forbid.transform(pd.DataFrame({"score": [np.nan, -5.0]}))
