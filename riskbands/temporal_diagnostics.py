"""
Detailed temporal diagnostics for binning behaviour across vintages.

This module adds an audit-friendly layer on top of the core temporal stability
utilities, focusing on variable/bin/time diagnostics useful in credit-risk and
PD workflows.
"""

from __future__ import annotations

from itertools import combinations

import numpy as np
import pandas as pd


EPSILON = 1e-9


def _require_fitted_binner(binner) -> pd.DataFrame:
    bin_summary = getattr(binner, "bin_summary", None)
    if bin_summary is None:
        raise RuntimeError("Binner ainda nao foi treinado.")
    return bin_summary


def _make_bin_reference(binner, variable: str) -> pd.DataFrame:
    bin_summary = _require_fitted_binner(binner)
    ref = bin_summary.loc[bin_summary["variable"] == variable].copy().reset_index(drop=True)
    if ref.empty:
        raise KeyError(f"Variable '{variable}' not found in bin_summary.")

    ref["bin"] = ref["bin"].astype(str)
    if "bin_code" not in ref.columns:
        for candidate in ("bin_code_float", "bin_code_int"):
            if candidate in ref.columns:
                ref["bin_code"] = ref[candidate]
                break
        else:
            ref["bin_code"] = ref.index.astype(float)
    if "bin_order" not in ref.columns:
        ref["bin_order"] = ref.index.astype(int)
    ref["transform_value"] = ref["bin"].astype(str)
    return ref[["variable", "bin_code", "bin", "bin_order", "transform_value"]]


def _resolve_expected_trend(binner, df_var: pd.DataFrame) -> str:
    if getattr(binner, "monotonic", None) in {"ascending", "descending"}:
        return binner.monotonic

    ref_rates = (
        df_var.groupby("bin_order")["event_rate"]
        .mean()
        .sort_index()
        .dropna()
    )
    if len(ref_rates) < 2:
        return "none"
    if ref_rates.is_monotonic_increasing:
        return "ascending"
    if ref_rates.is_monotonic_decreasing:
        return "descending"
    return "none"


def _pair_signs_from_rates(ref_rates: pd.Series) -> dict[tuple[int, int], float]:
    reference = {}
    for left, right in combinations(ref_rates.index.tolist(), 2):
        sign = float(np.sign(ref_rates.loc[left] - ref_rates.loc[right]))
        if sign != 0:
            reference[(left, right)] = sign
    return reference


def _build_reference_rank_signs(
    df_var: pd.DataFrame,
    *,
    time_col: str,
) -> dict[tuple[int, int], float]:
    ref_rates = (
        df_var.groupby("bin_order")["event_rate"]
        .mean()
        .sort_index()
        .dropna()
    )
    reference = _pair_signs_from_rates(ref_rates)
    if reference:
        return reference

    # When the global average collapses to ties, fall back to the first period
    # that still shows a clear ordering so reversals remain auditable.
    for _period, grp in df_var.groupby(time_col, sort=True):
        period_rates = (
            grp.loc[grp["coverage_flag"]]
            .set_index("bin_order")["event_rate"]
            .sort_index()
            .dropna()
        )
        reference = _pair_signs_from_rates(period_rates)
        if reference:
            return reference
    return {}


def _period_flags(
    df_var: pd.DataFrame,
    time_col: str,
    expected_trend: str,
    reference_rank_signs: dict[tuple[int, int], float],
) -> pd.DataFrame:
    records = []
    for period, grp in df_var.groupby(time_col, sort=True):
        covered = grp.loc[grp["coverage_flag"]].sort_values("bin_order")
        values = covered["event_rate"].dropna()

        monotonic_break = False
        if expected_trend == "ascending" and len(values) >= 2:
            monotonic_break = not values.is_monotonic_increasing
        elif expected_trend == "descending" and len(values) >= 2:
            monotonic_break = not values.is_monotonic_decreasing

        ranking_reversal = False
        if len(covered) >= 2 and reference_rank_signs:
            rates_by_order = covered.set_index("bin_order")["event_rate"].to_dict()
            for pair, reference_sign in reference_rank_signs.items():
                if pair[0] not in rates_by_order or pair[1] not in rates_by_order:
                    continue
                current_sign = float(np.sign(rates_by_order[pair[0]] - rates_by_order[pair[1]]))
                if current_sign != 0 and current_sign != reference_sign:
                    ranking_reversal = True
                    break

        records.append(
            {
                time_col: period,
                "period_monotonic_break_flag": monotonic_break,
                "period_ranking_reversal_flag": ranking_reversal,
            }
        )

    return pd.DataFrame(records)


def _attach_alert_flags(df: pd.DataFrame, flag_mapping: dict[str, str]) -> pd.Series:
    labels = []
    for _, row in df.iterrows():
        row_labels = [label for column, label in flag_mapping.items() if bool(row[column])]
        labels.append(";".join(row_labels))
    return pd.Series(labels, index=df.index, dtype="object")


def _safe_std(series: pd.Series) -> float:
    values = series.dropna()
    if len(values) <= 1:
        return 0.0
    return float(values.std(ddof=0))


def _temporal_score_from_diagnostics(
    df_var: pd.DataFrame,
    *,
    time_col: str,
    min_common_periods: int = 2,
    low_freq_penalty: float = 0.1,
    low_coverage_penalty: float = 0.1,
    inversion_penalty: float = 0.1,
) -> float:
    pivot = (
        df_var.pivot_table(index="bin_code", columns=time_col, values="event_rate")
        .sort_index(axis=1)
        .sort_index()
    )
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
            valid = diffs[mask]
            distances.append(float(np.abs(valid).mean()))
            non_zero_signs = np.sign(valid)
            non_zero_signs = non_zero_signs[non_zero_signs != 0]
            if np.unique(non_zero_signs).size > 1:
                inversion_count += 1

    score = float(np.mean(distances)) if distances else 0.0
    min_counts = (
        df_var.loc[df_var["coverage_flag"]]
        .groupby("bin_code")["total_count"]
        .min()
        .reindex(df_var["bin_code"].unique(), fill_value=0)
    )
    coverage = df_var.groupby("bin_code")["coverage_flag"].mean()
    score -= low_freq_penalty * int((min_counts < df_var["min_bin_count"].iloc[0]).sum())
    score -= low_coverage_penalty * int((coverage < df_var["min_time_coverage"].iloc[0]).sum())
    score -= inversion_penalty * inversion_count
    return float(score) if np.isfinite(score) else 0.0


def build_temporal_bin_diagnostics(
    binner,
    X: pd.DataFrame,
    y: pd.Series,
    *,
    time_col: str,
    dataset_name: str | None = None,
    min_bin_count: int = 30,
    min_bin_share: float = 0.05,
    min_time_coverage: float = 0.75,
) -> pd.DataFrame:
    """
    Build a detailed diagnostic table indexed conceptually by variable/bin/time.

    The output is audit-friendly and includes per-vintage event rate, share,
    WoE, IV contribution, coverage signals, and row-level alert flags.
    """
    _require_fitted_binner(binner)
    if time_col not in X.columns:
        raise KeyError(
            f"time_col='{time_col}' nao esta em X. Inclua a coluna de safra no DataFrame."
        )

    X_bins = binner.transform(X)
    periods = sorted(X[time_col].dropna().unique().tolist())
    diagnostics = []

    for variable in X_bins.columns:
        ref = _make_bin_reference(binner, variable)
        observed = pd.DataFrame(
            {
                time_col: X[time_col].values,
                "transform_value": pd.Series(X_bins[variable], index=X.index).astype(str).values,
                "target": y.values,
            }
        )

        agg = (
            observed.groupby([time_col, "transform_value"])["target"]
            .agg(total_count="count", event_count="sum")
            .reset_index()
        )
        agg["non_event_count"] = agg["total_count"] - agg["event_count"]

        grid = (
            pd.MultiIndex.from_product(
                [periods, ref["transform_value"].tolist()],
                names=[time_col, "transform_value"],
            )
            .to_frame(index=False)
        )
        df_var = grid.merge(agg, on=[time_col, "transform_value"], how="left")
        df_var[["total_count", "event_count", "non_event_count"]] = df_var[
            ["total_count", "event_count", "non_event_count"]
        ].fillna(0)
        df_var[["total_count", "event_count", "non_event_count"]] = df_var[
            ["total_count", "event_count", "non_event_count"]
        ].astype(int)
        df_var = df_var.merge(ref, on="transform_value", how="left")
        df_var["dataset"] = dataset_name

        period_totals = (
            df_var.groupby(time_col)[["total_count", "event_count", "non_event_count"]]
            .sum()
            .rename(
                columns={
                    "total_count": "_period_total_count",
                    "event_count": "_period_event_count",
                    "non_event_count": "_period_non_event_count",
                }
            )
            .reset_index()
        )
        df_var = df_var.merge(period_totals, on=time_col, how="left")
        df_var["coverage_flag"] = df_var["total_count"] > 0
        df_var["bin_share"] = np.where(
            df_var["_period_total_count"] > 0,
            df_var["total_count"] / df_var["_period_total_count"],
            np.nan,
        )
        df_var.loc[~df_var["coverage_flag"], "bin_share"] = 0.0
        df_var["event_rate"] = np.where(
            df_var["coverage_flag"],
            df_var["event_count"] / np.clip(df_var["total_count"], 1, None),
            np.nan,
        )

        event_prop = np.where(
            df_var["coverage_flag"],
            df_var["event_count"] / np.clip(df_var["_period_event_count"], 1, None),
            0.0,
        )
        non_event_prop = np.where(
            df_var["coverage_flag"],
            df_var["non_event_count"] / np.clip(df_var["_period_non_event_count"], 1, None),
            0.0,
        )
        df_var["woe"] = np.where(
            df_var["coverage_flag"],
            np.log(np.clip(event_prop, EPSILON, None) / np.clip(non_event_prop, EPSILON, None)),
            np.nan,
        )
        df_var["iv_contribution"] = np.where(
            df_var["coverage_flag"],
            (event_prop - non_event_prop) * df_var["woe"],
            0.0,
        )

        coverage_ratio = df_var.groupby("bin_code")["coverage_flag"].mean().rename("bin_coverage_ratio")
        df_var = df_var.merge(coverage_ratio.reset_index(), on="bin_code", how="left")

        df_var["rare_count_flag"] = df_var["coverage_flag"] & (df_var["total_count"] < min_bin_count)
        df_var["rare_share_flag"] = df_var["coverage_flag"] & (df_var["bin_share"] < min_bin_share)
        df_var["rare_bin_flag"] = df_var["rare_count_flag"] | df_var["rare_share_flag"]
        df_var["missing_bin_flag"] = ~df_var["coverage_flag"]
        df_var["low_coverage_flag"] = df_var["bin_coverage_ratio"] < min_time_coverage
        df_var["min_bin_count"] = min_bin_count
        df_var["min_time_coverage"] = min_time_coverage
        df_var["min_bin_share"] = min_bin_share

        expected_trend = _resolve_expected_trend(binner, df_var)
        reference_rank_signs = _build_reference_rank_signs(df_var, time_col=time_col)
        period_flags = _period_flags(df_var, time_col, expected_trend, reference_rank_signs)
        df_var = df_var.merge(period_flags, on=time_col, how="left")
        df_var["expected_trend"] = expected_trend

        flag_mapping = {
            "missing_bin_flag": "missing_bin",
            "rare_count_flag": "rare_count",
            "rare_share_flag": "rare_share",
            "low_coverage_flag": "low_coverage",
            "period_monotonic_break_flag": "monotonic_break",
            "period_ranking_reversal_flag": "ranking_reversal",
        }
        df_var["alert_flags"] = _attach_alert_flags(df_var, flag_mapping)

        diagnostics.append(
            df_var[
                [
                    "dataset",
                    "variable",
                    "bin_code",
                    "bin",
                    "bin_order",
                    time_col,
                    "total_count",
                    "event_count",
                    "non_event_count",
                    "bin_share",
                    "event_rate",
                    "woe",
                    "iv_contribution",
                    "coverage_flag",
                    "bin_coverage_ratio",
                    "rare_count_flag",
                    "rare_share_flag",
                    "rare_bin_flag",
                    "missing_bin_flag",
                    "low_coverage_flag",
                    "period_monotonic_break_flag",
                    "period_ranking_reversal_flag",
                    "expected_trend",
                    "alert_flags",
                    "min_bin_count",
                    "min_bin_share",
                    "min_time_coverage",
                ]
            ]
        )

    detailed = pd.concat(diagnostics, ignore_index=True)
    detailed.attrs["time_col"] = time_col
    detailed.attrs["dataset"] = dataset_name
    return detailed.sort_values(["variable", "bin_order", time_col]).reset_index(drop=True)


def summarize_temporal_variable_stability(
    diagnostics: pd.DataFrame,
    *,
    time_col: str | None = None,
    event_rate_std_threshold: float = 0.05,
    woe_std_threshold: float = 0.5,
    bin_share_std_threshold: float = 0.05,
) -> pd.DataFrame:
    """
    Aggregate the detailed diagnostics into a variable-level stability summary.
    """
    if diagnostics.empty:
        return pd.DataFrame()

    time_col = time_col or diagnostics.attrs.get("time_col")
    if not time_col or time_col not in diagnostics.columns:
        raise ValueError("time_col must be provided or present in diagnostics attrs.")

    summaries = []
    for variable, df_var in diagnostics.groupby("variable", sort=False):
        by_bin = df_var.groupby(["bin_code", "bin"], sort=True)
        coverage_ratio = by_bin["coverage_flag"].mean()
        event_rate_std = by_bin["event_rate"].apply(_safe_std)
        woe_std = by_bin["woe"].apply(_safe_std)
        bin_share_std = by_bin["bin_share"].apply(_safe_std)
        rare_bin_count = int(by_bin["rare_bin_flag"].any().sum())

        period_flags = (
            df_var.groupby(time_col)[
                ["period_monotonic_break_flag", "period_ranking_reversal_flag"]
            ]
            .max()
            .reset_index()
        )

        alert_flags = []
        if rare_bin_count > 0:
            alert_flags.append("rare_bins")
        low_coverage_bin_count = int((coverage_ratio < df_var["min_time_coverage"].iloc[0]).sum())
        if low_coverage_bin_count > 0:
            alert_flags.append("low_coverage")
        if event_rate_std.max() > event_rate_std_threshold:
            alert_flags.append("event_rate_volatility")
        if woe_std.max() > woe_std_threshold:
            alert_flags.append("woe_volatility")
        if bin_share_std.max() > bin_share_std_threshold:
            alert_flags.append("share_instability")

        monotonic_break_period_count = int(period_flags["period_monotonic_break_flag"].sum())
        ranking_reversal_period_count = int(period_flags["period_ranking_reversal_flag"].sum())
        if monotonic_break_period_count > 0:
            alert_flags.append("monotonic_break")
        if ranking_reversal_period_count > 0:
            alert_flags.append("ranking_reversal")

        summaries.append(
            {
                "dataset": df_var["dataset"].iloc[0],
                "variable": variable,
                "n_bins_effective": int(by_bin["coverage_flag"].any().sum()),
                "n_periods": int(df_var[time_col].nunique()),
                "expected_trend": df_var["expected_trend"].iloc[0],
                "coverage_ratio_mean": float(coverage_ratio.mean()),
                "coverage_ratio_min": float(coverage_ratio.min()),
                "bins_missing_any_period_count": int((coverage_ratio < 1.0).sum()),
                "missing_period_count": int((~df_var["coverage_flag"]).sum()),
                "low_coverage_bin_count": low_coverage_bin_count,
                "rare_bin_count": rare_bin_count,
                "event_rate_std_mean": float(event_rate_std.mean()),
                "event_rate_std_max": float(event_rate_std.max()),
                "woe_std_mean": float(woe_std.mean()),
                "woe_std_max": float(woe_std.max()),
                "bin_share_std_mean": float(bin_share_std.mean()),
                "bin_share_std_max": float(bin_share_std.max()),
                "monotonic_break_period_count": monotonic_break_period_count,
                "ranking_reversal_period_count": ranking_reversal_period_count,
                "temporal_score": _temporal_score_from_diagnostics(df_var, time_col=time_col),
                "alert_flags": ";".join(alert_flags),
            }
        )

    summary = pd.DataFrame(summaries).sort_values("variable").reset_index(drop=True)
    summary.attrs["time_col"] = time_col
    return summary


