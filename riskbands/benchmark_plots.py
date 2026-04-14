"""Reusable Plotly figures for benchmark-style credit-risk demos."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
import re
from typing import Any

import numpy as np
import pandas as pd

try:  # pragma: no cover
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
except ImportError:  # pragma: no cover
    go = None
    make_subplots = None


_INTERVAL_RE = re.compile(
    r"^\s*[\(\[]\s*(?P<left>-?inf|[-+]?\d*\.?\d+)\s*,\s*(?P<right>-?inf|[-+]?\d*\.?\d+)\s*[\)\]]\s*$"
)

APPROACH_COLORS = {
    "OptimalBinning puro": "#8B1E3F",
    "RiskBands estatico": "#28536B",
    "RiskBands selecionado": "#2A7F62",
}


def _require_plotly() -> None:
    if go is None or make_subplots is None:
        raise ImportError(
            "Plotly is required for benchmark visuals. Install with 'pip install -e .[viz]' "
            "or 'pip install plotly'."
        )


def _to_percent(values: Iterable[float]) -> list[float]:
    return (pd.Series(values, dtype="float64") * 100.0).round(3).tolist()


def _approach_color(label: str) -> str:
    return APPROACH_COLORS.get(label, "#607D8B")


def _ordered_bins(diagnostics: pd.DataFrame) -> list[str]:
    if "bin_order" in diagnostics.columns:
        labels = (
            diagnostics[["bin_order", "bin"]]
            .drop_duplicates()
            .sort_values("bin_order")["bin"]
            .astype(str)
            .tolist()
        )
        if labels:
            return labels
    return diagnostics["bin"].astype(str).drop_duplicates().tolist()


def extract_numeric_cut_edges(bin_labels: Iterable[str]) -> list[float]:
    edges = set()
    for label in bin_labels:
        match = _INTERVAL_RE.match(str(label))
        if not match:
            continue
        for side in ("left", "right"):
            raw = match.group(side).strip().lower()
            if raw in {"-inf", "+inf", "inf"}:
                continue
            edges.add(float(raw))
    return sorted(edges)


def plot_benchmark_board(board: pd.DataFrame, *, title: str) -> Any:
    _require_plotly()
    df = board.copy()
    columns = [
        "approach_label",
        "candidate_name",
        "iv",
        "temporal_score",
        "objective_score",
        "total_penalty",
        "coverage_ratio_min",
        "rare_bin_count",
        "ranking_reversal_period_count",
        "alert_flags",
    ]
    for column in ("iv", "temporal_score", "objective_score", "total_penalty", "coverage_ratio_min"):
        df[column] = df[column].map(lambda v: f"{float(v):.3f}")
    df["rare_bin_count"] = df["rare_bin_count"].astype(int).astype(str)
    df["ranking_reversal_period_count"] = df["ranking_reversal_period_count"].astype(int).astype(str)
    fill = ["#DFF3EA" if flag else "#FFFFFF" for flag in df["selected_by_riskbands"].tolist()]
    fig = go.Figure(
        data=[
            go.Table(
                header=dict(
                    values=[column.replace("_", "<br>").title() for column in columns],
                    fill_color="#163A5F",
                    font=dict(color="white", size=12),
                    align="left",
                ),
                cells=dict(
                    values=[df[column].tolist() for column in columns],
                    fill_color=[fill],
                    align="left",
                    font=dict(size=11),
                    height=28,
                ),
            )
        ]
    )
    fig.update_layout(title=title, height=360, margin=dict(l=10, r=10, t=70, b=10))
    return fig


def plot_metric_bars(board: pd.DataFrame, *, title: str, metrics: list[dict[str, Any]]) -> Any:
    _require_plotly()
    fig = make_subplots(
        rows=1,
        cols=len(metrics),
        subplot_titles=[metric["label"] for metric in metrics],
        horizontal_spacing=0.08,
    )
    for idx, metric in enumerate(metrics, start=1):
        values = board[metric["column"]].astype(float).tolist()
        y = _to_percent(values) if metric.get("percent") else values
        text = [
            f"{value * 100:.1f}%" if metric.get("percent") else f"{value:.3f}"
            for value in values
        ]
        fig.add_trace(
            go.Bar(
                x=board["approach_label"].tolist(),
                y=y,
                text=text,
                textposition="outside",
                marker_color=[_approach_color(label) for label in board["approach_label"]],
                showlegend=False,
                hovertemplate="%{x}<br>%{text}<extra></extra>",
            ),
            row=1,
            col=idx,
        )
    fig.update_layout(
        title=title,
        height=420,
        plot_bgcolor="white",
        paper_bgcolor="white",
        margin=dict(l=30, r=30, t=80, b=50),
    )
    fig.update_xaxes(tickangle=-25)
    return fig


def plot_event_rate_curves_by_approach(
    diagnostics_by_approach: dict[str, pd.DataFrame],
    *,
    time_col: str,
    title: str,
) -> Any:
    _require_plotly()
    approaches = list(diagnostics_by_approach)
    fig = make_subplots(
        rows=len(approaches),
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        subplot_titles=approaches,
    )
    for row_idx, approach in enumerate(approaches, start=1):
        diagnostics = diagnostics_by_approach[approach]
        ordered_bins = _ordered_bins(diagnostics)
        mean_rates = diagnostics.groupby("bin")["event_rate"].mean().reindex(ordered_bins).fillna(0.0)
        palette = [f"rgba(2,48,89,{alpha:.2f})" for alpha in np.linspace(0.35, 0.95, len(mean_rates))]
        color_map = {
            label: palette[idx]
            for idx, label in enumerate(mean_rates.sort_values().index.tolist())
        }
        for bin_label in ordered_bins:
            grp = diagnostics.loc[diagnostics["bin"].astype(str) == str(bin_label)].sort_values(time_col)
            fig.add_trace(
                go.Scatter(
                    x=grp[time_col].astype(str).tolist(),
                    y=_to_percent(grp["event_rate"]),
                    mode="lines+markers",
                    name=str(bin_label),
                    legendgroup=str(bin_label),
                    showlegend=row_idx == 1,
                    line=dict(color=color_map.get(str(bin_label), "#607D8B"), width=2),
                    marker=dict(size=7),
                    hovertemplate=f"{approach}<br>Bin={bin_label}<br>Vintage=%{{x}}<br>Event rate=%{{y:.2f}}%<extra></extra>",
                ),
                row=row_idx,
                col=1,
            )
        fig.update_yaxes(title_text="Event rate (%)", row=row_idx, col=1)
    fig.update_layout(
        title=title,
        height=max(360, 290 * len(approaches)),
        plot_bgcolor="white",
        paper_bgcolor="white",
        margin=dict(l=50, r=30, t=90, b=60),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0.0),
    )
    fig.update_xaxes(title_text="Vintage")
    return fig


def plot_event_rate_heatmap(
    diagnostics: pd.DataFrame,
    *,
    time_col: str,
    title: str,
    value_col: str = "event_rate",
) -> Any:
    _require_plotly()
    ordered_bins = _ordered_bins(diagnostics)
    pivot = (
        diagnostics.assign(bin=diagnostics["bin"].astype(str))
        .pivot_table(index="bin", columns=time_col, values=value_col)
        .reindex(ordered_bins)
    )
    values = pivot.to_numpy(dtype=float)
    colorbar_title = value_col.replace("_", " ")
    if value_col == "event_rate":
        values = values * 100.0
        colorbar_title = "Event rate (%)"
    fig = go.Figure(
        data=[
            go.Heatmap(
                z=values,
                x=[str(column) for column in pivot.columns.tolist()],
                y=pivot.index.tolist(),
                colorscale="Teal",
                colorbar=dict(title=colorbar_title),
                hovertemplate="Bin=%{y}<br>Vintage=%{x}<br>Value=%{z:.2f}<extra></extra>",
            )
        ]
    )
    fig.update_layout(
        title=title,
        height=340,
        plot_bgcolor="white",
        paper_bgcolor="white",
        margin=dict(l=40, r=20, t=70, b=40),
    )
    return fig


def plot_penalty_breakdown(board: pd.DataFrame, *, title: str) -> Any:
    _require_plotly()
    penalty_columns = [
        "rare_bin_penalty",
        "coverage_gap_penalty",
        "event_rate_volatility_penalty",
        "woe_volatility_penalty",
        "share_volatility_penalty",
        "monotonic_break_penalty",
        "ranking_reversal_penalty",
        "temporal_shortfall_penalty",
        "temporal_variance_penalty",
        "window_drift_penalty",
        "rank_inversion_penalty",
        "separation_penalty",
        "entropy_penalty",
        "psi_penalty",
    ]
    available = [column for column in penalty_columns if column in board.columns]
    long = board[["approach_label"] + available].melt(
        id_vars="approach_label",
        var_name="penalty",
        value_name="value",
    )
    if (long["value"] > 0).any():
        long = long.loc[long["value"] > 0].copy()
    long["penalty"] = long["penalty"].str.replace("_penalty", "", regex=False).str.replace("_", " ")
    fig = go.Figure()
    for approach_label, grp in long.groupby("approach_label", sort=False):
        fig.add_trace(
            go.Bar(
                x=grp["penalty"].tolist(),
                y=grp["value"].astype(float).tolist(),
                name=approach_label,
                marker_color=_approach_color(approach_label),
                hovertemplate="%{x}<br>%{y:.3f}<extra>" + approach_label + "</extra>",
            )
        )
    fig.update_layout(
        title=title,
        barmode="group",
        height=420,
        plot_bgcolor="white",
        paper_bgcolor="white",
        margin=dict(l=30, r=30, t=80, b=80),
        xaxis_title="Penalty component",
        yaxis_title="Penalty value",
    )
    fig.update_xaxes(tickangle=-30)
    return fig


def plot_score_distribution_with_cutpoints(
    panel: pd.DataFrame,
    *,
    value_col: str,
    time_col: str,
    bin_labels: Iterable[str] | None = None,
    cut_edges: Iterable[float] | None = None,
    title: str,
) -> Any:
    _require_plotly()
    edges = (
        sorted({float(edge) for edge in cut_edges})
        if cut_edges is not None
        else extract_numeric_cut_edges(bin_labels or [])
    )
    fig = go.Figure()
    months = sorted(panel[time_col].dropna().unique().tolist())
    palette = ["#163A5F", "#1F7A8C", "#3BA99C", "#A4D4AE", "#F6AE2D", "#E4572E"]
    for idx, month in enumerate(months):
        subset = panel.loc[panel[time_col] == month, value_col].astype(float)
        fig.add_trace(
            go.Histogram(
                x=subset.tolist(),
                name=str(month),
                histnorm="probability density",
                opacity=0.45,
                marker_color=palette[idx % len(palette)],
                hovertemplate=f"Vintage {month}<br>{value_col}=%{{x:.2f}}<br>Density=%{{y:.3f}}<extra></extra>",
            )
        )
    for edge in edges:
        fig.add_vline(x=edge, line_width=2, line_dash="dash", line_color="#8B1E3F", opacity=0.9)
    fig.update_layout(
        title=title,
        barmode="overlay",
        height=420,
        plot_bgcolor="white",
        paper_bgcolor="white",
        margin=dict(l=40, r=20, t=70, b=40),
        xaxis_title=value_col.replace("_", " ").title(),
        yaxis_title="Density",
    )
    return fig


def plot_aggregate_vs_vintage_gap(diagnostics: pd.DataFrame, *, time_col: str, title: str) -> Any:
    _require_plotly()
    ordered_bins = _ordered_bins(diagnostics)
    aggregate = (
        diagnostics.groupby("bin", dropna=False)[["event_count", "total_count"]]
        .sum()
        .assign(event_rate=lambda df: df["event_count"] / df["total_count"].replace(0, np.nan))
        .reindex(ordered_bins)
        ["event_rate"]
        .fillna(0.0)
    )
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=ordered_bins,
            y=_to_percent(aggregate),
            name="Agregado",
            marker_color="#D6E8F2",
            hovertemplate="Bin=%{x}<br>Aggregate=%{y:.2f}%<extra></extra>",
        )
    )
    months = sorted(diagnostics[time_col].dropna().unique().tolist())
    palette = ["#163A5F", "#1F7A8C", "#3BA99C", "#F6AE2D", "#E4572E", "#8B1E3F"]
    for idx, month in enumerate(months):
        grp = diagnostics.loc[diagnostics[time_col] == month].copy()
        grp["bin"] = grp["bin"].astype(str)
        grp = grp.set_index("bin").reindex(ordered_bins).reset_index()
        fig.add_trace(
            go.Scatter(
                x=ordered_bins,
                y=_to_percent(grp["event_rate"]),
                mode="markers+lines",
                name=str(month),
                marker=dict(size=8, color=palette[idx % len(palette)]),
                line=dict(width=1.5, color=palette[idx % len(palette)]),
                hovertemplate=f"Vintage {month}<br>Bin=%{{x}}<br>Event rate=%{{y:.2f}}%<extra></extra>",
            )
        )
    fig.update_layout(
        title=title,
        height=420,
        plot_bgcolor="white",
        paper_bgcolor="white",
        margin=dict(l=40, r=20, t=70, b=40),
        xaxis_title="Bin",
        yaxis_title="Event rate (%)",
    )
    return fig


def plot_sampling_preview(preview: pd.DataFrame, *, title: str) -> Any:
    _require_plotly()
    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=("Target rate by vintage", "Volume by vintage"),
        horizontal_spacing=0.12,
    )
    months = preview["month"].astype(str).tolist()
    fig.add_trace(
        go.Scatter(x=months, y=_to_percent(preview["raw_target_rate"]), mode="lines+markers", name="Raw target rate", line=dict(color="#8B1E3F", width=2)),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(x=months, y=_to_percent(preview["sampled_target_rate"]), mode="lines+markers", name="Sampled target rate", line=dict(color="#2A7F62", width=2)),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Bar(x=months, y=preview["raw_count"].astype(int).tolist(), name="Raw count", marker_color="#D6E8F2"),
        row=1,
        col=2,
    )
    fig.add_trace(
        go.Bar(x=months, y=preview["sampled_count"].fillna(0).astype(int).tolist(), name="Sampled count", marker_color="#6BAED6"),
        row=1,
        col=2,
    )
    fig.update_yaxes(title_text="Target rate (%)", row=1, col=1)
    fig.update_yaxes(title_text="Rows", row=1, col=2)
    fig.update_layout(
        title=title,
        height=400,
        barmode="group",
        plot_bgcolor="white",
        paper_bgcolor="white",
        margin=dict(l=40, r=20, t=70, b=40),
    )
    return fig


def export_figure_pack(figures: dict[str, Any], output_dir: str | Path, *, prefix: str) -> list[str]:
    _require_plotly()
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, figure in figures.items():
        if figure is None:
            continue
        target = target_dir / f"{prefix}_{name}.html"
        html = figure.to_html(include_plotlyjs="cdn", full_html=True)
        html = html.replace(
            "<head>",
            '<head>\n<meta name="robots" content="noindex" />',
            1,
        )
        html = html.replace(
            "<body>",
            '<body data-pagefind-ignore="all">',
            1,
        )
        target.write_text(html, encoding="utf-8")
        written.append(str(target))
    return written
