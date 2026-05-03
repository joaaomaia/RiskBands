"""Visualization helpers for temporal stability and audit-friendly plots."""

from __future__ import annotations

import math

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns


def _get_bin_summary(binner) -> pd.DataFrame:
    bin_summary = getattr(binner, "bin_summary", None)
    if bin_summary is None:
        raise RuntimeError("Binner ainda nao foi treinado.")
    return bin_summary


def _bin_event_rate_map(binner, var: str) -> dict[str, float]:
    """Return {bin_label: average_event_rate} for a feature."""
    bin_summary = _get_bin_summary(binner)
    bs = (
        bin_summary[bin_summary["variable"] == var]
        .loc[~bin_summary["bin"].astype(str).str.contains("Special|Missing", case=False, na=False)]
        .copy()
    )
    return {str(row["bin"]): float(row["event_rate"]) for _, row in bs.iterrows()}


def _infer_bin_label_map(var: str, grp: pd.DataFrame, label_mapper):
    """Align bin identifiers from the pivot table with labels from the fitted binner."""
    base_map = label_mapper(var)
    unique_codes = grp["bin"].astype(str).unique().tolist()

    if all(code in base_map for code in unique_codes):
        return {code: str(base_map[code]) for code in unique_codes}

    base_values = {str(value) for value in base_map.values()}
    if all(code in base_values for code in unique_codes):
        return {code: code for code in unique_codes}

    return {code: code for code in unique_codes}


def _remove_background_grid(ax):
    ax.grid(False)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)


def _format_time_axis(ax, ordered_periods: list[int | str], label: str | None):
    xticklabels = [str(v) for v in ordered_periods]
    ax.set_xticks(range(len(ordered_periods)))
    ax.set_xticklabels(xticklabels, rotation=0)
    if label:
        ax.set_xlabel(label)


def _place_legend_bottom(ax, n_items: int, *, title: str = "Bin"):
    ncol = max(1, min(n_items, 4))
    ax.legend(
        title=title,
        bbox_to_anchor=(0.5, -0.25),
        loc="upper center",
        ncol=ncol,
        frameon=False,
    )


HEX_BASE = "#023059"
HEX_MID = "#2A7F62"
HEX_MIN = "#D7E5EF"


def _blend_palette(n: int) -> list[str]:
    if n <= 0:
        return []
    return sns.blend_palette([HEX_MIN, HEX_BASE], n, as_cmap=False)


def _finish_figure(fig: plt.Figure) -> plt.Figure:
    fig.tight_layout()
    return fig


def _finalize_plot_payload(figures: dict[str, plt.Figure]):
    if not figures:
        raise ValueError("No plottable data was found for the requested feature(s).")
    if len(figures) == 1:
        return next(iter(figures.values()))
    return figures


def _ordered_bins_from_diagnostics(grp: pd.DataFrame) -> list[str]:
    if "bin_order" in grp.columns:
        ordered = (
            grp[["bin_order", "bin"]]
            .drop_duplicates()
            .sort_values("bin_order")["bin"]
            .astype(str)
            .tolist()
        )
        if ordered:
            return ordered
    return grp["bin"].astype(str).drop_duplicates().tolist()


def plot_event_rate_stability(
    pivot: pd.DataFrame,
    *,
    binner,
    label_mapper=None,
    title_prefix: str | None = "Estabilidade temporal",
    time_col_label: str | None = None,
    figsize=(14, 6),
):
    """Plot event-rate curves by bin for each feature in the pivot table."""
    if label_mapper is None:
        def label_mapper(var):
            return binner._bin_code_to_label(var)

    df_long = (
        pivot.reset_index()
        .melt(id_vars=["variable", "bin"], var_name="safra", value_name="event_rate")
        .dropna(subset=["event_rate"])
    )

    figures = {}
    for var, grp in df_long.groupby("variable", sort=False):
        code2label = _infer_bin_label_map(var, grp, label_mapper)
        grp = grp.assign(BinLabel=grp["bin"].astype(str).map(code2label))
        grp = grp[~grp["BinLabel"].str.contains("Special|Missing", case=False, na=False)]
        if grp.empty:
            continue

        er_map = _bin_event_rate_map(binner, var)
        ordered_labels = [
            label
            for label in er_map
            if label in set(grp["BinLabel"].tolist())
        ] or grp["BinLabel"].drop_duplicates().tolist()
        color_map = dict(zip(ordered_labels, _blend_palette(len(ordered_labels)), strict=False))
        ordered_periods = sorted(grp["safra"].unique())

        fig, ax = plt.subplots(figsize=figsize)
        for label in ordered_labels:
            g = grp.loc[grp["BinLabel"] == label].set_index("safra").reindex(ordered_periods).reset_index()
            if g["event_rate"].notna().sum() == 0:
                continue
            ax.plot(
                range(len(ordered_periods)),
                g["event_rate"] * 100,
                marker="o",
                linewidth=2.0,
                label=label,
                color=color_map[label],
            )

        prefix = f"{title_prefix} - " if title_prefix else ""
        ax.set_title(f"{prefix}{var}")
        ax.set_ylabel("Event rate (%)")
        _format_time_axis(ax, ordered_periods, time_col_label or "Safra")
        _place_legend_bottom(ax, n_items=len(ordered_labels))
        _remove_background_grid(ax)
        figures[var] = _finish_figure(fig)

    if not figures:
        raise ValueError("No plottable data was found for the requested feature(s).")
    return figures


def plot_metric_over_time(
    diagnostics: pd.DataFrame,
    *,
    time_col: str,
    value_col: str,
    title_prefix: str | None,
    ylabel: str,
    legend_title: str = "Bin",
    percent: bool = False,
    figsize: tuple[float, float] = (13.5, 6.5),
):
    """Plot a temporal metric by bin for each selected feature."""
    if diagnostics.empty:
        raise ValueError("Temporal diagnostics are empty. Compute diagnostics before plotting.")

    figures = {}
    for variable, grp in diagnostics.groupby("variable", sort=False):
        ordered_bins = _ordered_bins_from_diagnostics(grp)
        ordered_periods = sorted(grp[time_col].dropna().unique().tolist())
        palette = dict(zip(ordered_bins, _blend_palette(len(ordered_bins)), strict=False))

        fig, ax = plt.subplots(figsize=figsize)
        plotted = 0
        for bin_label in ordered_bins:
            line = (
                grp.loc[grp["bin"].astype(str) == str(bin_label), [time_col, value_col]]
                .sort_values(time_col)
                .set_index(time_col)
                .reindex(ordered_periods)
                .reset_index()
            )
            if line[value_col].notna().sum() == 0:
                continue
            y_values = line[value_col].astype(float)
            if percent:
                y_values = y_values * 100.0
            ax.plot(
                range(len(ordered_periods)),
                y_values,
                marker="o",
                linewidth=2.0,
                label=str(bin_label),
                color=palette[str(bin_label)],
            )
            plotted += 1

        if plotted == 0:
            plt.close(fig)
            continue

        prefix = f"{title_prefix} - " if title_prefix else ""
        ax.set_title(f"{prefix}{variable}")
        ax.set_ylabel(ylabel)
        _format_time_axis(ax, ordered_periods, time_col)
        _place_legend_bottom(ax, n_items=plotted, title=legend_title)
        _remove_background_grid(ax)
        figures[variable] = _finish_figure(fig)

    return _finalize_plot_payload(figures)


def plot_metric_heatmap(
    diagnostics: pd.DataFrame,
    *,
    time_col: str,
    value_col: str,
    title_prefix: str | None,
    colorbar_label: str,
    percent: bool = False,
    figsize: tuple[float, float] = (12.5, 6.0),
    annotate: bool = True,
):
    """Render a feature-wise heatmap from the temporal diagnostics layer."""
    if diagnostics.empty:
        raise ValueError("Temporal diagnostics are empty. Compute diagnostics before plotting.")

    figures = {}
    for variable, grp in diagnostics.groupby("variable", sort=False):
        ordered_bins = _ordered_bins_from_diagnostics(grp)
        pivot = (
            grp.assign(bin=grp["bin"].astype(str))
            .pivot_table(index="bin", columns=time_col, values=value_col, aggfunc="first")
            .reindex(ordered_bins)
        )
        if pivot.empty:
            continue

        values = pivot.copy()
        if percent:
            values = values * 100.0

        fig, ax = plt.subplots(figsize=figsize)
        sns.heatmap(
            values,
            cmap=sns.color_palette("crest", as_cmap=True),
            annot=annotate,
            fmt=".1f" if percent else ".2f",
            linewidths=0.4,
            linecolor="white",
            mask=values.isna(),
            cbar_kws={"label": colorbar_label},
            ax=ax,
        )
        prefix = f"{title_prefix} - " if title_prefix else ""
        ax.set_title(f"{prefix}{variable}")
        ax.set_xlabel(time_col)
        ax.set_ylabel("Bin")
        figures[variable] = _finish_figure(fig)

    return _finalize_plot_payload(figures)


def _format_label(column: str) -> str:
    return column.replace("_", " ").replace("objective ", "").strip().title()


def plot_score_components(
    score_row: pd.Series,
    audit_row: pd.Series | None = None,
    *,
    title: str | None = None,
    figsize: tuple[float, float] = (13.5, 7.5),
):
    """Plot weighted objective components alongside the effective score weights."""
    feature_name = str(score_row.get("variable", "feature"))
    contributions = []
    if audit_row is not None:
        for column, value in audit_row.items():
            if not isinstance(column, str):
                continue
            if not (column.endswith("_component") or column.endswith("_penalty")):
                continue
            if column.startswith("objective_"):
                continue
            numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
            if pd.isna(numeric) or math.isclose(float(numeric), 0.0, abs_tol=1e-12):
                continue
            kind = "Reward" if column.endswith("_component") else "Penalty"
            contributions.append(
                {
                    "label": _format_label(column.replace("_component", "").replace("_penalty", "")),
                    "value": float(numeric),
                    "kind": kind,
                }
            )

    weight_rows = []
    for column, value in score_row.items():
        if not isinstance(column, str) or not column.startswith("objective_weight_"):
            continue
        numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
        if pd.isna(numeric):
            continue
        weight_rows.append(
            {
                "label": _format_label(column.replace("objective_weight_", "")),
                "value": float(numeric),
            }
        )

    fig, axes = plt.subplots(1, 2, figsize=figsize, gridspec_kw={"width_ratios": [1.35, 1.0]})

    if contributions:
        contribution_df = pd.DataFrame(contributions).sort_values("value")
        colors = contribution_df["kind"].map({"Reward": HEX_MID, "Penalty": "#C05A44"})
        axes[0].barh(contribution_df["label"], contribution_df["value"], color=colors)
    else:
        axes[0].text(0.5, 0.5, "No weighted components available", ha="center", va="center")
        axes[0].set_yticks([])
    axes[0].set_title("Weighted Contributions")
    axes[0].set_xlabel("Contribution")
    _remove_background_grid(axes[0])

    if weight_rows:
        weights_df = pd.DataFrame(weight_rows).sort_values("value")
        axes[1].barh(weights_df["label"], weights_df["value"], color=HEX_BASE)
    else:
        axes[1].text(0.5, 0.5, "No score weights available", ha="center", va="center")
        axes[1].set_yticks([])
    axes[1].set_title("Score Weights")
    axes[1].set_xlabel("Weight")
    _remove_background_grid(axes[1])

    fig.suptitle(
        title
        or (
            f"Score components - {feature_name} "
            f"(score={float(score_row.get('objective_score', np.nan)):.3f}, "
            f"strategy={score_row.get('score_strategy', 'n/a')})"
        ),
        y=1.02,
    )
    return _finish_figure(fig)


def plot_bin_summary_metric(
    table: pd.DataFrame,
    *,
    feature_name: str,
    value_col: str,
    ylabel: str,
    title: str,
    percent: bool = False,
    figsize: tuple[float, float] = (11.5, 5.5),
):
    """Plot a metric already available on the binning summary."""
    if table.empty:
        raise ValueError(f"No binning table is available for feature '{feature_name}'.")

    values = table[value_col].astype(float)
    if percent:
        values = values * 100.0

    fig, ax = plt.subplots(figsize=figsize)
    sns.barplot(
        data=table.assign(_value=values, _bin=table["bin"].astype(str)),
        x="_bin",
        y="_value",
        palette=_blend_palette(len(table)),
        ax=ax,
    )
    ax.set_title(title)
    ax.set_xlabel("Bin")
    ax.set_ylabel(ylabel)
    ax.tick_params(axis="x", rotation=20)
    _remove_background_grid(ax)
    return _finish_figure(fig)


def plot_bin_diagnostics_metric(
    diagnostics: pd.DataFrame,
    *,
    feature_name: str,
    value_col: str,
    ylabel: str,
    title: str,
    percent: bool = False,
    figsize: tuple[float, float] = (11.5, 5.5),
):
    """Plot a metric aggregated from the detailed temporal diagnostics table."""
    if diagnostics.empty:
        raise ValueError(f"No diagnostics are available for feature '{feature_name}'.")

    ordered = _ordered_bins_from_diagnostics(diagnostics)
    aggregated = (
        diagnostics.groupby(["bin_order", "bin"], sort=True)[value_col]
        .mean()
        .reset_index()
        .sort_values("bin_order")
    )
    values = aggregated[value_col].astype(float)
    if percent:
        values = values * 100.0

    fig, ax = plt.subplots(figsize=figsize)
    sns.barplot(
        data=aggregated.assign(_value=values, _bin=aggregated["bin"].astype(str)),
        x="_bin",
        y="_value",
        order=ordered,
        palette=_blend_palette(len(aggregated)),
        ax=ax,
    )
    ax.set_title(title)
    ax.set_xlabel("Bin")
    ax.set_ylabel(ylabel)
    ax.tick_params(axis="x", rotation=20)
    _remove_background_grid(ax)
    return _finish_figure(fig)
