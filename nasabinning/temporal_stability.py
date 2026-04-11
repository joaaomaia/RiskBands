"""
Temporal stability utilities for bin diagnostics.

The main indicator is ``temporal_separability_score``, which measures how
consistently event-rate curves stay separated across time periods.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import ks_2samp


def event_rate_by_time(
    bin_tbl: pd.DataFrame,
    time_col: str,
    *,
    fill_value: float | None = None,
) -> pd.DataFrame:
    """
    Build an event-rate pivot table indexed by ``(variable, bin)``.
    """
    df = bin_tbl.copy()
    df["event_rate"] = df["event"] / df["count"]

    pivot_kwargs = {
        "index": ["variable", "bin"],
        "columns": time_col,
        "values": "event_rate",
    }
    if fill_value is not None:
        pivot_kwargs["fill_value"] = fill_value

    return df.pivot_table(**pivot_kwargs).sort_index(axis=1).sort_index()


def stability_table(pivot: pd.DataFrame) -> pd.DataFrame:
    """Return simple temporal dispersion metrics for each bin."""
    if pivot.empty:
        return pd.DataFrame(columns=["std", "range", "coverage", "observed_periods"])

    std = pivot.std(axis=1, skipna=True)
    rng = pivot.max(axis=1, skipna=True) - pivot.min(axis=1, skipna=True)
    coverage = pivot.notna().mean(axis=1)
    observed_periods = pivot.notna().sum(axis=1)
    return pd.DataFrame(
        {
            "std": std,
            "range": rng,
            "coverage": coverage,
            "observed_periods": observed_periods,
        }
    )


def psi_over_time(pivot: pd.DataFrame) -> float:
    """Compute PSI between the first and last observed time periods."""
    if pivot.shape[1] < 2:
        return 0.0

    from .metrics import psi

    first, last = pivot.columns[0], pivot.columns[-1]
    df_tmp = pd.DataFrame(
        {
            "expected": pivot[first].fillna(0.0).values,
            "actual": pivot[last].fillna(0.0).values,
        }
    )
    return psi(df_tmp)


def ks_over_time(pivot: pd.DataFrame) -> float:
    """Compute KS between the first and last observed event-rate distributions."""
    if pivot.shape[1] < 2:
        return 0.0

    first, last = pivot.columns[0], pivot.columns[-1]
    first_values = pivot[first].dropna().values
    last_values = pivot[last].dropna().values
    if len(first_values) == 0 or len(last_values) == 0:
        return 0.0
    return float(ks_2samp(first_values, last_values).statistic)


def temporal_separability_score(
    df: pd.DataFrame,
    variable: str,
    bin_col: str,
    target_col: str,
    time_col: str,
    *,
    penalize_inversions: bool = False,
    penalize_low_freq: bool = False,
    penalize_low_coverage: bool = False,
    min_bin_count: int = 30,
    min_time_coverage: float = 0.5,
    min_common_periods: int = 2,
    low_freq_penalty: float = 0.1,
    low_coverage_penalty: float = 0.1,
    inversion_penalty: float = 0.1,
) -> float:
    """
    Calculate temporal separability between bins.

    The base score is the mean absolute distance between all valid pairs of
    bin event-rate curves. Sparse combinations are handled explicitly: only
    overlapping periods are compared, and pairs with too little overlap are
    ignored. Optional penalties can discourage bins with low support, low time
    coverage, or ranking reversals across periods.
    """
    tbl = (
        df.groupby([bin_col, time_col])[target_col]
        .agg(["sum", "count"])
        .reset_index()
        .rename(columns={"sum": "event"})
    )
    tbl["variable"] = variable

    pivot = event_rate_by_time(tbl, time_col)
    if pivot.shape[0] < 2:
        return 0.0

    curves = pivot.to_numpy(dtype=float)
    distances = []
    inversion_count = 0

    for i in range(pivot.shape[0]):
        for j in range(i + 1, pivot.shape[0]):
            diffs = curves[i] - curves[j]
            mask = np.isfinite(diffs)
            if mask.sum() < min_common_periods:
                continue

            valid_diffs = diffs[mask]
            distances.append(float(np.abs(valid_diffs).mean()))

            if penalize_inversions:
                non_zero_signs = np.sign(valid_diffs)
                non_zero_signs = non_zero_signs[non_zero_signs != 0]
                if np.unique(non_zero_signs).size > 1:
                    inversion_count += 1

    score = float(np.mean(distances)) if distances else 0.0

    if penalize_low_freq:
        min_counts = tbl.groupby(bin_col)["count"].min()
        score -= low_freq_penalty * int((min_counts < min_bin_count).sum())

    if penalize_low_coverage:
        coverage = pivot.notna().mean(axis=1)
        score -= low_coverage_penalty * int((coverage < min_time_coverage).sum())

    if penalize_inversions:
        score -= inversion_penalty * inversion_count

    if not np.isfinite(score):
        return 0.0
    return float(score)
