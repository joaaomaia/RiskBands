import numpy as np
import pandas as pd

from nasabinning.temporal_stability import (
    event_rate_by_time,
    psi_over_time,
    stability_table,
    temporal_separability_score,
)


def test_event_rate_pivot_and_psi():
    data = []
    for safra in [202301, 202302]:
        for b in range(3):
            data.append(
                dict(
                    variable="x",
                    bin=b,
                    event=np.random.randint(10, 30),
                    count=100,
                    AnoMesReferencia=safra,
                )
            )
    df = pd.DataFrame(data)
    pivot = event_rate_by_time(df, "AnoMesReferencia")
    assert pivot.shape == (3, 2)
    assert psi_over_time(pivot) >= 0

    table = stability_table(pivot)
    assert {"std", "range", "coverage", "observed_periods"} <= set(table.columns)


def test_temporal_separability_score_detects_clear_separation():
    df = pd.DataFrame(
        {
            "bin": [0, 0, 1, 1] * 3,
            "target": [0, 0, 1, 1] * 3,
            "time": [202301] * 4 + [202302] * 4 + [202303] * 4,
        }
    )
    score = temporal_separability_score(df, "x", "bin", "target", "time")
    assert score > 0.9


def test_temporal_separability_score_handles_sparse_bins_and_penalties():
    df = pd.DataFrame(
        {
            "bin": [0, 0, 0, 1, 1, 2, 2, 2],
            "target": [0, 1, 0, 1, 1, 0, 0, 0],
            "time": [202301, 202302, 202303, 202301, 202302, 202302, 202303, 202304],
        }
    )

    base_score = temporal_separability_score(
        df,
        "x",
        "bin",
        "target",
        "time",
        min_common_periods=1,
    )
    penalized_score = temporal_separability_score(
        df,
        "x",
        "bin",
        "target",
        "time",
        penalize_low_freq=True,
        penalize_low_coverage=True,
        min_common_periods=1,
        min_bin_count=2,
        min_time_coverage=0.75,
    )

    assert np.isfinite(base_score)
    assert np.isfinite(penalized_score)
    assert penalized_score <= base_score
