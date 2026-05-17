import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from riskbands import Binner, RiskBands


def make_monotonic_frame(n=240, seed=41):
    rng = np.random.default_rng(seed)
    score = rng.normal(size=n)
    logits = score + rng.normal(scale=0.25, size=n)
    target = (logits > 0).astype(int)
    return pd.DataFrame({"score": score, "target": target})


def fit_score_binner(**kwargs):
    df = make_monotonic_frame()
    binner = RiskBands(strategy="supervised", max_bins=kwargs.pop("max_bins", 4), min_event_rate_diff=0.0, **kwargs)
    binner.fit(df, y="target", column="score")
    return binner, df


def test_min_n_bins_none_preserves_existing_binning_behavior():
    df = make_monotonic_frame()
    previous = Binner(strategy="supervised", max_bins=4, min_event_rate_diff=0.0)
    explicit_none = RiskBands(strategy="supervised", max_bins=4, min_event_rate_diff=0.0, min_n_bins=None)

    previous.fit(df, y="target", column="score")
    explicit_none.fit(df, y="target", column="score")

    assert_frame_equal(previous.binning_table(), explicit_none.binning_table())
    assert_frame_equal(previous.transform(df[["score"]]), explicit_none.transform(df[["score"]]))
    assert explicit_none.min_n_bins_metadata_ is None


def test_valid_min_n_bins_is_accepted_and_reported():
    binner, _ = fit_score_binner(min_n_bins=2)

    assert binner.min_n_bins == 2
    assert binner.get_params()["min_n_bins"] == 2
    assert binner.min_n_bins_metadata_["min_n_bins"] == 2
    assert "min_n_bins_metadata" in binner.metadata_


@pytest.mark.parametrize("value", [0, -1, 1.5, "2", True])
def test_invalid_min_n_bins_is_rejected(value):
    with pytest.raises(ValueError, match="min_n_bins"):
        RiskBands(min_n_bins=value)


def test_set_params_rejects_invalid_min_n_bins():
    with pytest.raises(ValueError, match="min_n_bins"):
        RiskBands().set_params(min_n_bins=0)


def test_variable_reaching_min_n_bins_has_ok_status():
    binner, _ = fit_score_binner(min_n_bins=2, max_bins=4)

    metadata = binner.min_n_bins_metadata_
    assert metadata["min_n_bins_reached"] is True
    assert metadata["min_n_bins_status"] == "ok"
    assert metadata["n_regular_bins"] >= 2
    assert binner.min_n_bins_report_.iloc[0]["min_n_bins_status"] == "ok"


def test_variable_below_min_n_bins_gets_alert_without_artificial_cuts():
    binner, _ = fit_score_binner(min_n_bins=4, max_bins=2)

    metadata = binner.min_n_bins_metadata_
    assert metadata["min_n_bins_reached"] is False
    assert metadata["min_n_bins_status"] == "below_minimum"
    assert "no artificial cuts" in metadata["variables"][0]["min_n_bins_reason"]
    assert metadata["n_regular_bins"] <= 2
    assert binner.binning_table()["bin"].nunique() <= 2


def test_missing_and_special_bins_do_not_count_as_regular_bins():
    summary = pd.DataFrame(
        {
            "variable": ["score", "score", "score", "score"],
            "bin": ["(-inf, 0.0]", "Missing", "Special", "(0.0, inf)"],
            "count": [50, 3, 2, 45],
        }
    )

    assert RiskBands._count_regular_bins(summary) == 2
