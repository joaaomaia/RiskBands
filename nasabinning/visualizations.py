"""
Visualization helpers for temporal stability plots.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


def _get_bin_summary(binner) -> pd.DataFrame:
    bin_summary = getattr(binner, "bin_summary", None)
    if bin_summary is None:
        raise RuntimeError("Binner ainda nao foi treinado.")
    return bin_summary


def _bin_event_rate_map(binner, var: str) -> dict[str, float]:
    """
    Return {bin_label: average_event_rate} for a feature.
    """
    bin_summary = _get_bin_summary(binner)
    bs = (
        bin_summary[bin_summary["variable"] == var]
        .loc[~bin_summary["bin"].isin(["Special", "Missing"])]
        .copy()
    )
    return {str(row["bin"]): row["event_rate"] for _, row in bs.iterrows()}


def _infer_bin_label_map(var: str, grp: pd.DataFrame, label_mapper):
    """
    Align bin codes from the pivot table with labels from the fitted binner.
    """
    base_map = label_mapper(var)
    unique_codes = sorted(grp["bin"].unique())

    if all(code in base_map for code in unique_codes):
        return {code: base_map[code] for code in unique_codes}

    return {code: base_map[idx] for idx, code in enumerate(unique_codes)}


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


def _place_legend_bottom(ax, n_items: int):
    ncol = max(1, min(n_items, 4))
    ax.legend(
        title="Bin",
        bbox_to_anchor=(0.5, -0.25),
        loc="upper center",
        ncol=ncol,
        frameon=False,
    )


HEX_BASE = "#023059"
HEX_MIN = "#B5C1CD"


def _blend_palette(n: int) -> list[str]:
    if n <= 0:
        return []
    return sns.blend_palette([HEX_MIN, HEX_BASE], n, as_cmap=False)


def plot_event_rate_stability(
    pivot: pd.DataFrame,
    *,
    binner,
    label_mapper=None,
    title_prefix: str | None = "Estabilidade temporal",
    time_col_label: str | None = None,
    figsize=(14, 6),
):
    """
    Plot event-rate curves by bin for each feature in the pivot table.
    """
    if label_mapper is None:
        label_mapper = lambda var: binner._bin_code_to_label(var)

    df_long = (
        pivot.reset_index()
        .melt(id_vars=["variable", "bin"], var_name="safra", value_name="event_rate")
        .dropna(subset=["event_rate"])
    )

    figures = []
    for var, grp in df_long.groupby("variable", sort=False):
        code2label = _infer_bin_label_map(var, grp, label_mapper)
        grp = grp.assign(BinLabel=grp["bin"].map(code2label))
        grp = grp[~grp["BinLabel"].str.contains("Special|Missing", case=False, na=False)]
        if grp.empty:
            continue

        er_map = _bin_event_rate_map(binner, var)
        er_map = {label: er_map.get(label, float("nan")) for label in grp["BinLabel"].unique()}

        ordered_labels = sorted(er_map, key=lambda x: (pd.isna(er_map[x]), er_map[x]))
        color_map = dict(zip(ordered_labels, _blend_palette(len(ordered_labels))))
        ordered_periods = sorted(grp["safra"].unique())

        fig, ax = plt.subplots(figsize=figsize)
        for label, g in grp.groupby("BinLabel"):
            g_plot = g.set_index("safra").reindex(ordered_periods).reset_index()
            ax.plot(
                range(len(ordered_periods)),
                g_plot["event_rate"] * 100,
                marker="o",
                linewidth=1.5,
                label=label,
                color=color_map[label],
            )

        prefix = f"{title_prefix} - " if title_prefix else ""
        ax.set_title(f"{prefix}{var}")
        ax.set_ylabel("Event Rate (%)")
        _format_time_axis(ax, ordered_periods, time_col_label or "Safra")
        _place_legend_bottom(ax, n_items=len(ordered_labels))
        _remove_background_grid(ax)
        plt.tight_layout()
        plt.show()
        figures.append(fig)

    return figures
