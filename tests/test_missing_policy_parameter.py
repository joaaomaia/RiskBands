import pytest

from riskbands import Binner, RiskBands
from tests.test_missing_values_current_behavior import fit_categorical_missing_binner


def test_missing_policy_default_is_standard():
    binner = RiskBands()

    assert binner.missing_policy == "standard"
    assert binner.missing_policy_ == "standard"
    assert binner.get_params()["missing_policy"] == "standard"


@pytest.mark.parametrize("policy", ["standard", "separate_bin", "forbid"])
def test_missing_policy_accepts_supported_values(policy):
    binner = Binner(missing_policy=policy)

    assert binner.missing_policy == policy
    assert binner.missing_policy_ == policy


def test_missing_policy_rejects_invalid_value():
    with pytest.raises(ValueError, match="Unsupported missing_policy"):
        RiskBands(missing_policy="merge_nearest_woe")


def test_missing_policy_is_available_through_riskbands_alias():
    assert RiskBands is Binner
    assert RiskBands(missing_policy="separate_bin").missing_policy == "separate_bin"


def test_standard_missing_policy_preserves_categorical_current_behavior():
    binner, df = fit_categorical_missing_binner()
    standard = RiskBands(
        strategy="supervised",
        max_bins=4,
        min_event_rate_diff=0.0,
        force_categorical=["grade"],
        missing_policy="standard",
    )
    standard.fit(df, y="target", column="grade")

    assert standard.transform(df[["grade"]]).equals(binner.transform(df[["grade"]]))
