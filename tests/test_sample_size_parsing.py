import pytest

from riskbands import RiskBands


def test_sample_size_default_absolute_is_valid():
    binner = RiskBands()

    assert binner.sample_size == 10_000
    assert binner.sampling_metadata_["sample_size_requested"] == 10_000
    assert binner.sampling_metadata_["sample_size_type"] == "absolute"


def test_sample_size_integer_is_absolute_row_count():
    binner = RiskBands(sample_size=1)
    plan = binner._resolve_sampling_plan(population_size=10)

    assert plan["sample_size_requested"] == 1
    assert plan["sample_size_type"] == "absolute"
    assert plan["sample_size_effective"] == 1
    assert plan["sample_fraction_effective"] == 0.1


def test_sample_size_fraction_is_fractional_plan():
    binner = RiskBands(sample_size=0.05)
    plan = binner._resolve_sampling_plan(population_size=1_000)

    assert plan["sample_size_requested"] == 0.05
    assert plan["sample_size_type"] == "fraction"
    assert plan["sample_fraction_effective"] == 0.05
    assert plan["sample_size_effective"] == 50


def test_sample_size_float_one_means_full_fraction():
    binner = RiskBands(sample_size=1.0)
    plan = binner._resolve_sampling_plan(population_size=17)

    assert plan["sample_size_requested"] == 1.0
    assert plan["sample_size_type"] == "fraction"
    assert plan["sample_fraction_effective"] == 1.0
    assert plan["sample_size_effective"] == 17


@pytest.mark.parametrize("value", [0, -1, 1.5, "10000", None, True])
def test_invalid_sample_size_is_rejected(value):
    with pytest.raises(ValueError, match="sample_size"):
        RiskBands(sample_size=value)


def test_set_params_validates_sample_size():
    binner = RiskBands()

    binner.set_params(sample_size=0.25)
    assert binner.sample_size == 0.25

    with pytest.raises(ValueError, match="sample_size"):
        binner.set_params(sample_size=0)


def test_absolute_sample_size_larger_than_population_caps_at_population():
    binner = RiskBands(sample_size=10_000)
    plan = binner._resolve_sampling_plan(population_size=125)

    assert plan["sample_size_requested"] == 10_000
    assert plan["sample_size_type"] == "absolute"
    assert plan["sample_size_effective"] == 125
    assert plan["sample_fraction_effective"] == 1.0


def test_sampling_metadata_is_refreshed_after_fit():
    import numpy as np
    import pandas as pd

    rng = np.random.default_rng(61)
    df = pd.DataFrame({"score": rng.normal(size=80)})
    df["target"] = (df["score"] > 0).astype(int)
    binner = RiskBands(strategy="supervised", max_bins=3, min_event_rate_diff=0.0, sample_size=20)

    binner.fit(df, y="target", column="score")

    assert binner.sampling_metadata_["input_backend"] == "pandas"
    assert binner.sampling_metadata_["fit_backend"] == "pandas_core"
    assert binner.sampling_metadata_["fit_mode"] == "pandas_core"
    assert binner.sampling_metadata_["sampling_applied"] is False
    assert binner.sampling_metadata_["sampling_strategy"] == "none"
    assert binner.sampling_metadata_["n_rows_source"] == 80
    assert binner.sampling_metadata_["n_rows_fit"] == 80
    assert binner.metadata_["sampling_metadata"]["sample_size_requested"] == 20
