from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

import riskbands
from riskbands import BinComparator, Binner, ks_over_time, psi_over_time, temporal_separability_score


def _build_dataset(seed: int = 7, n: int = 320) -> tuple[pd.DataFrame, pd.Series]:
    rng = np.random.default_rng(seed)
    df = pd.DataFrame(
        {
            "score": rng.normal(size=n),
            "income_ratio": rng.normal(loc=0.0, scale=1.1, size=n),
            "month": rng.choice([202301, 202302, 202303, 202304], size=n),
        }
    )
    proba = 0.25 + 0.18 * df["score"] - 0.06 * df["income_ratio"] + 0.01 * (df["month"] - 202301)
    proba = np.clip(proba, 0.01, 0.99)
    y = pd.Series((rng.random(n) < proba).astype(int), name="target")
    return df, y


def run_base_smoke(expected_version: str | None) -> None:
    print(f"riskbands import version: {riskbands.__version__}")
    if expected_version and riskbands.__version__ != expected_version:
        raise SystemExit(
            f"Installed version mismatch: expected {expected_version}, got {riskbands.__version__}"
        )

    x, y = _build_dataset()

    binner = Binner(
        strategy="supervised",
        check_stability=True,
        monotonic="ascending",
        min_event_rate_diff=0.02,
        max_bins=5,
    )
    transformed = binner.fit_transform(x, y, time_col="month")
    diagnostics = binner.temporal_bin_diagnostics(x, y, time_col="month", dataset_name="smoke")
    summary = binner.temporal_variable_summary(diagnostics=diagnostics, time_col="month")

    comparator = BinComparator(
        [
            {
                "strategy": "supervised",
                "max_bins": 5,
                "min_event_rate_diff": 0.02,
                "name": "supervised_reference",
            },
            {
                "strategy": "unsupervised",
                "method": "quantile",
                "n_bins": 5,
                "name": "quantile_reference",
            },
        ]
    )
    comparison = comparator.fit_compare(x[["score"]], y)

    temporal_panel = pd.DataFrame(
        [
            {"variable": "score", "bin": 0, "event": 15, "count": 100, "month": 202301},
            {"variable": "score", "bin": 1, "event": 29, "count": 100, "month": 202301},
            {"variable": "score", "bin": 0, "event": 17, "count": 100, "month": 202304},
            {"variable": "score", "bin": 1, "event": 31, "count": 100, "month": 202304},
        ]
    )
    pivot = (
        temporal_panel.assign(event_rate=lambda df: df["event"] / df["count"])
        .pivot_table(index=["variable", "bin"], columns="month", values="event_rate")
        .sort_index(axis=1)
        .sort_index()
    )

    separability = temporal_separability_score(
        pd.DataFrame(
            {
                "bin": [0, 0, 1, 1] * 2,
                "target": [0, 0, 1, 1] * 2,
                "month": [202301] * 4 + [202304] * 4,
            }
        ),
        "score",
        "bin",
        "target",
        "month",
    )

    if transformed.empty or diagnostics.empty or summary.empty:
        raise SystemExit("Base smoke failed: expected fitted outputs to be non-empty.")
    if comparison.empty or {"supervised_reference", "quantile_reference"} - set(comparison.index):
        raise SystemExit("Base smoke failed: comparison output is incomplete.")

    print(
        "base smoke OK:",
        {
            "rows": int(len(transformed)),
            "summary_rows": int(len(summary)),
            "comparison_rows": int(len(comparison)),
            "ks_over_time": float(ks_over_time(pivot)),
            "psi_over_time": float(psi_over_time(pivot)),
            "temporal_separability_score": float(separability),
        },
    )


def run_viz_smoke() -> None:
    from riskbands.benchmark_plots import export_figure_pack, plot_metric_bars

    board = pd.DataFrame(
        {
            "approach_label": ["RiskBands estatico", "RiskBands selecionado"],
            "objective_score": [0.412, 0.438],
            "temporal_score": [0.287, 0.351],
        }
    )
    figure = plot_metric_bars(
        board,
        title="RiskBands smoke benchmark",
        metrics=[
            {"column": "objective_score", "label": "Objective score"},
            {"column": "temporal_score", "label": "Temporal score"},
        ],
    )
    with tempfile.TemporaryDirectory(prefix="riskbands-smoke-") as tmpdir:
        written = export_figure_pack({"metric_comparison": figure}, Path(tmpdir), prefix="smoke")
        if len(written) != 1 or not Path(written[0]).exists():
            raise SystemExit("Viz smoke failed: expected exported HTML artifact.")
    print("viz smoke OK:", {"exported_files": 1})


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke test an installed RiskBands package.")
    parser.add_argument("--expected-version", default=None)
    parser.add_argument("--check-viz", action="store_true")
    args = parser.parse_args()

    run_base_smoke(args.expected_version)
    if args.check_viz:
        run_viz_smoke()


if __name__ == "__main__":
    main()
