import pytest

from riskbands import Binner, RiskBands


def test_missing_merge_defaults_do_not_change_standard_policy():
    binner = RiskBands()

    assert binner.missing_policy == "standard"
    assert binner.missing_policy_ == "standard"
    assert binner.missing_merge_criterion is None
    assert binner.missing_merge_criterion_ is None
    assert binner.missing_merge_fallback == "separate_bin"
    assert binner.missing_merge_fallback_ == "separate_bin"
    assert binner.get_params()["missing_policy"] == "standard"
    assert binner.get_params()["missing_merge_criterion"] is None
    assert binner.get_params()["missing_merge_fallback"] == "separate_bin"


def test_missing_merge_nearest_event_rate_is_accepted():
    binner = RiskBands(
        missing_policy="merge",
        missing_merge_criterion="nearest_event_rate",
    )

    assert binner.missing_policy == "merge"
    assert binner.missing_policy_ == "merge"
    assert binner.effective_missing_policy_ == "merge"
    assert binner.missing_merge_criterion == "nearest_event_rate"
    assert binner.missing_merge_criterion_ == "nearest_event_rate"
    assert binner.missing_merge_fallback == "separate_bin"


def test_missing_merge_accepts_raise_fallback():
    binner = Binner(
        missing_policy="merge",
        missing_merge_criterion="nearest_event_rate",
        missing_merge_fallback="raise",
    )

    assert binner.missing_merge_fallback == "raise"
    assert binner.missing_merge_fallback_ == "raise"


def test_missing_policy_merge_requires_criterion():
    with pytest.raises(ValueError, match="missing_merge_criterion.*required"):
        RiskBands(missing_policy="merge")


def test_missing_merge_rejects_invalid_criterion():
    with pytest.raises(ValueError, match="Unsupported missing_merge_criterion"):
        RiskBands(
            missing_policy="merge",
            missing_merge_criterion="nearest_woe",
        )


def test_missing_merge_rejects_invalid_fallback():
    with pytest.raises(ValueError, match="Unsupported missing_merge_fallback"):
        RiskBands(
            missing_policy="merge",
            missing_merge_criterion="nearest_event_rate",
            missing_merge_fallback="standard",
        )


@pytest.mark.parametrize("policy", ["standard", "separate_bin", "forbid"])
def test_missing_merge_criterion_is_rejected_without_merge_policy(policy):
    with pytest.raises(ValueError, match="missing_merge_criterion.*missing_policy='merge'"):
        RiskBands(
            missing_policy=policy,
            missing_merge_criterion="nearest_event_rate",
        )


def test_legacy_alias_remains_standard_without_merge_params():
    binner = RiskBands(missing_policy="legacy")

    assert binner.missing_policy == "standard"
    assert binner.missing_policy_ == "standard"
    assert binner.missing_merge_criterion is None


def test_legacy_alias_rejects_merge_criterion():
    with pytest.raises(ValueError, match="missing_merge_criterion.*missing_policy='merge'"):
        RiskBands(
            missing_policy="legacy",
            missing_merge_criterion="nearest_event_rate",
        )


def test_set_params_validates_missing_merge_contract():
    binner = RiskBands()

    binner.set_params(
        missing_policy="merge",
        missing_merge_criterion="nearest_event_rate",
        missing_merge_fallback="raise",
    )

    assert binner.missing_policy == "merge"
    assert binner.missing_merge_criterion == "nearest_event_rate"
    assert binner.missing_merge_fallback == "raise"


def test_set_params_rejects_incompatible_criterion():
    binner = RiskBands(
        missing_policy="merge",
        missing_merge_criterion="nearest_event_rate",
    )

    with pytest.raises(ValueError, match="missing_merge_criterion.*missing_policy='merge'"):
        binner.set_params(missing_policy="standard")
