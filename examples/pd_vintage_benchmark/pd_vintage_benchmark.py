"""Premium PD vintage benchmark for RiskBands."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import logging
from pathlib import Path
import re
import sys
from typing import Any
import warnings

import numpy as np
import pandas as pd
from optbinning import OptimalBinning


def _patch_pandas_settingwithcopywarning() -> None:
    if not hasattr(pd.errors, "SettingWithCopyWarning"):
        class SettingWithCopyWarning(Warning):
            pass

        pd.errors.SettingWithCopyWarning = SettingWithCopyWarning  # type: ignore[attr-defined]


_patch_pandas_settingwithcopywarning()
warnings.filterwarnings(
    "ignore",
    message=".*force_all_finite.*",
    category=FutureWarning,
)
warnings.filterwarnings(
    "ignore",
    message=".*quantile_method='linear'.*",
    category=FutureWarning,
)

ROOT = Path(__file__).resolve().parents[2]
RAW_MATERIAL = ROOT / "research" / "raw_material"
for candidate_path in (ROOT, RAW_MATERIAL):
    if str(candidate_path) not in sys.path:
        sys.path.insert(0, str(candidate_path))

from credit_data_sampler import TargetSampler
from credit_data_synthesizer import build_riskbands_pd_example_frame
from riskbands.benchmark_plots import (
    extract_numeric_cut_edges,
    export_figure_pack,
    plot_aggregate_vs_vintage_gap,
    plot_benchmark_board,
    plot_event_rate_curves_by_approach,
    plot_event_rate_heatmap,
    plot_metric_bars,
    plot_penalty_breakdown,
    plot_sampling_preview,
    plot_score_distribution_with_cutpoints,
)
from riskbands.compare import BinComparator
from riskbands.metrics import iv as compute_iv
from riskbands.reporting import (
    build_candidate_profile_report,
    build_candidate_winner_report,
    build_variable_audit_report,
)
from riskbands.temporal_diagnostics import (
    build_temporal_bin_diagnostics,
    summarize_temporal_variable_stability,
)
from riskbands.temporal_stability import event_rate_by_time


_SEGMENT_RE = re.compile(r"(\d+)$")
ANCHOR_SCENARIO = "temporal_reversal"


@dataclass(frozen=True)
class ScenarioSpec:
    name: str
    title: str
    description: str
    drift_strength: float
    reversal_strength: float
    composition_strength: float = 0.0


SCENARIOS: dict[str, ScenarioSpec] = {
    "stable_credit": ScenarioSpec(
        name="stable_credit",
        title="Stable Credit",
        description=(
            "Mild drift and mostly monotonic ordering. The static solution can stay competitive "
            "and RiskBands may simply validate that choice."
        ),
        drift_strength=0.15,
        reversal_strength=0.00,
        composition_strength=0.00,
    ),
    "temporal_reversal": ScenarioSpec(
        name="temporal_reversal",
        title="Temporal Reversal",
        description=(
            "Later vintages deteriorate in the overlap zone and partially invert the aggregate "
            "ordering, exposing why static IV alone can be misleading in credit."
        ),
        drift_strength=0.30,
        reversal_strength=1.25,
        composition_strength=0.15,
    ),
    "composition_shift": ScenarioSpec(
        name="composition_shift",
        title="Composition Shift",
        description=(
            "Later vintages over-represent the overlap zone and shrink the tails, pushing static "
            "cuts into lower coverage and more fragile bin shares."
        ),
        drift_strength=0.24,
        reversal_strength=0.55,
        composition_strength=0.90,
    ),
}

DEFAULT_SCENARIOS = tuple(SCENARIOS)
BENCHMARK_OBJECTIVE_KWARGS: dict[str, Any] = {
    "base_weights": {
        "separability": 0.20,
        "iv": 0.20,
        "ks": 0.05,
        "temporal_score": 0.55,
    },
    "penalty_weights": {
        "coverage_gap": 0.35,
        "event_rate_volatility": 0.35,
        "woe_volatility": 0.12,
        "share_volatility": 0.25,
        "ranking_reversals": 0.12,
        "temporal_shortfall": 0.80,
    },
    "minimums": {
        "iv": 0.02,
        "temporal_score": 0.10,
        "coverage_ratio": 0.80,
    },
}


def _safe_sigmoid(values: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-values))


def _ordered_segments(values: pd.Series) -> list[str]:
    def key_fn(value: str) -> tuple[int, str]:
        match = _SEGMENT_RE.search(str(value))
        return (int(match.group(1)) if match else 999, str(value))

    return sorted(values.dropna().astype(str).unique().tolist(), key=key_fn)


def _segment_weight_map(values: pd.Series) -> dict[str, float]:
    ordered = _ordered_segments(values)
    weights = np.linspace(0.50, -0.22, num=max(1, len(ordered)))
    return {label: float(weight) for label, weight in zip(ordered, weights)}


def _apply_composition_shift(
    panel: pd.DataFrame,
    *,
    scenario: ScenarioSpec,
    seed: int,
    samples_per_period: int,
) -> pd.DataFrame:
    if scenario.composition_strength <= 0:
        return panel.copy()

    rng = np.random.default_rng(seed + 97)
    periods = sorted(panel["month"].unique().tolist())
    shifted = []
    for idx, period in enumerate(periods):
        grp = panel.loc[panel["month"] == period].copy().reset_index(drop=True)
        weights = np.ones(len(grp), dtype="float64")
        overlap_mask = grp["bureau_score"].between(-0.15, 0.95)
        high_tail_mask = grp["bureau_score"] > 1.25
        low_tail_mask = grp["bureau_score"] < -0.90
        if idx >= len(periods) - 2:
            weights = np.where(overlap_mask, 1.0 + 2.4 * scenario.composition_strength, weights)
            weights = np.where(high_tail_mask, 0.35, weights)
            weights = np.where(low_tail_mask, 0.55, weights)
        elif idx == 0:
            weights = np.where(high_tail_mask, 1.15, weights)

        sampled = grp.sample(
            n=samples_per_period,
            replace=True,
            weights=weights,
            random_state=int(rng.integers(0, 1_000_000)),
        ).reset_index(drop=True)
        sampled["id_contrato"] = [f"{period}-SHIFT-{i:06d}" for i in range(len(sampled))]
        shifted.append(sampled)
    return pd.concat(shifted, ignore_index=True)


def _scenario_target_probabilities(panel: pd.DataFrame, scenario: ScenarioSpec) -> np.ndarray:
    periods = sorted(panel["month"].unique().tolist())
    period_index_map = {period: idx for idx, period in enumerate(periods)}
    period_index = panel["month"].map(period_index_map).astype(int).to_numpy(dtype=float)
    score = panel["bureau_score"].to_numpy(dtype=float)
    segment_weights = panel["risk_segment"].map(_segment_weight_map(panel["risk_segment"])).to_numpy(dtype=float)

    late_mask = period_index >= max(2, len(periods) - 2)
    overlap_mask = (score > -0.05) & (score < 1.00)
    high_tail_mask = score > 1.20
    mid_tail_mask = (score > 0.25) & (score < 0.75)

    logits = -2.55 + 1.08 * score + segment_weights + scenario.drift_strength * period_index
    if scenario.reversal_strength > 0:
        logits += scenario.reversal_strength * late_mask * overlap_mask
        logits -= 0.90 * scenario.reversal_strength * late_mask * high_tail_mask
        logits += 0.35 * scenario.reversal_strength * late_mask * mid_tail_mask
    if scenario.composition_strength > 0:
        logits += (
            0.35
            * scenario.composition_strength
            * late_mask
            * panel["risk_segment"].isin(["GH2", "GH3"]).to_numpy()
        )
        logits += 0.55 * scenario.composition_strength * late_mask * overlap_mask
    return _safe_sigmoid(logits)


def build_credit_benchmark_panel(
    *,
    scenario: str = ANCHOR_SCENARIO,
    seed: int = 73,
    samples_per_period: int = 220,
) -> pd.DataFrame:
    if scenario not in SCENARIOS:
        raise KeyError(f"Unknown scenario '{scenario}'. Available: {sorted(SCENARIOS)}")

    spec = SCENARIOS[scenario]
    panel = build_riskbands_pd_example_frame(
        random_seed=seed,
        periods=[202301, 202302, 202303, 202304, 202305, 202306],
        samples_per_period=samples_per_period,
        n_groups=4,
    )
    panel = _apply_composition_shift(
        panel,
        scenario=spec,
        seed=seed,
        samples_per_period=samples_per_period,
    )
    rng = np.random.default_rng(seed + 13)
    probabilities = _scenario_target_probabilities(panel, spec)

    panel = panel.copy()
    panel["target"] = (rng.random(len(panel)) < probabilities).astype(int)
    panel["scenario"] = spec.name
    panel["scenario_title"] = spec.title
    panel["scenario_description"] = spec.description
    panel["period_index"] = panel["month"].rank(method="dense").astype(int) - 1
    panel["score_zone"] = np.select(
        [
            panel["bureau_score"] < -0.90,
            panel["bureau_score"].between(-0.05, 1.00),
            panel["bureau_score"] > 1.20,
        ],
        ["low_tail", "overlap_zone", "high_tail"],
        default="mid_transition",
    )
    return panel.sort_values(["month", "bureau_score"]).reset_index(drop=True)


def build_sampling_preview(
    panel: pd.DataFrame,
    *,
    target_ratio: float = 0.30,
    seed: int = 73,
) -> pd.DataFrame:
    sampler = TargetSampler(
        target_ratio=target_ratio,
        keep_positives=True,
        per_group=False,
        strategy="undersample",
    )
    original_level = sampler.logger.level
    sampler.logger.setLevel(logging.ERROR)
    balanced, _overflow = sampler.fit_transform(
        panel,
        target_col="target",
        safra_col="month",
        group_col="risk_segment",
        random_state=seed,
    )
    sampler.logger.setLevel(original_level)

    raw_by_month = panel.groupby("month")["target"].agg(["mean", "size"])
    sampled_by_month = balanced.groupby("month")["target"].agg(["mean", "size"])
    return pd.DataFrame(
        {
            "month": raw_by_month.index,
            "raw_target_rate": raw_by_month["mean"].values,
            "sampled_target_rate": sampled_by_month["mean"].reindex(raw_by_month.index).values,
            "raw_count": raw_by_month["size"].values,
            "sampled_count": sampled_by_month["size"].reindex(raw_by_month.index).values,
        }
    ).reset_index(drop=True)


class DirectOptimalBinningBaseline:
    """Adapter for evaluating pure OptimalBinning with RiskBands diagnostics."""

    def __init__(
        self,
        *,
        variable: str = "bureau_score",
        max_bins: int = 6,
        monotonic_trend: str | None = None,
    ) -> None:
        self.variable = variable
        self.max_bins = max_bins
        self.monotonic = monotonic_trend
        self.monotonic_trend = monotonic_trend
        self.strategy = "optimal_binning_direct"
        self.time_col = None
        self.bin_summary = None

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "DirectOptimalBinningBaseline":
        if self.variable not in X.columns:
            raise KeyError(f"Variable '{self.variable}' not found in X.")

        self.model_ = OptimalBinning(
            name=self.variable,
            solver="cp",
            max_n_bins=self.max_bins,
            monotonic_trend=self.monotonic_trend,
        )
        values = X[self.variable].to_numpy()
        self.model_.fit(values, y.to_numpy())

        frame = pd.DataFrame(
            {
                "variable": self.variable,
                "bin_code": pd.Series(
                    self.model_.transform(values, metric="indices"),
                    index=X.index,
                ).astype("float64"),
                "bin": pd.Series(self.model_.transform(values, metric="bins"), index=X.index).astype(str),
                "target": y.to_numpy(),
            }
        )
        summary = (
            frame.groupby(["variable", "bin_code", "bin"], dropna=False)["target"]
            .agg(count="count", event="sum")
            .reset_index()
        )
        summary["non_event"] = summary["count"] - summary["event"]
        summary["event_rate"] = summary["event"] / summary["count"]
        summary = summary.sort_values("bin_code").reset_index(drop=True)
        self.bin_summary = summary
        self.iv_by_variable_ = pd.Series({self.variable: compute_iv(summary)}, name="iv")
        self.iv_ = float(self.iv_by_variable_.sum())
        return self

    def transform(self, X: pd.DataFrame, *, return_woe: bool = False) -> pd.DataFrame:
        metric = "woe" if return_woe else "indices"
        transformed = self.model_.transform(X[self.variable].to_numpy(), metric=metric)
        return pd.DataFrame({self.variable: transformed}, index=X.index)

    def _bin_code_to_label(self, variable: str) -> dict[float, str]:
        if variable != self.variable or self.bin_summary is None:
            raise KeyError(f"Variable '{variable}' not available in this baseline.")
        rows = self.bin_summary.sort_values("bin_code")
        return {float(row["bin_code"]): str(row["bin"]) for _, row in rows.iterrows()}

    def stability_over_time(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        *,
        time_col: str,
        fill_value: float | None = None,
    ) -> pd.DataFrame:
        bins = self.transform(X)[self.variable]
        tbl = (
            pd.DataFrame(
                {
                    "variable": self.variable,
                    "bin": bins,
                    time_col: X[time_col].values,
                    "target": y.values,
                }
            )
            .groupby(["variable", "bin", time_col])["target"]
            .agg(["sum", "count"])
            .reset_index()
            .rename(columns={"sum": "event"})
        )
        pivot = event_rate_by_time(tbl, time_col, fill_value=fill_value)
        self._pivot_ = pivot
        self.time_col = time_col
        return pivot

    def temporal_bin_diagnostics(self, X: pd.DataFrame, y: pd.Series, **kwargs: Any) -> pd.DataFrame:
        diagnostics = build_temporal_bin_diagnostics(self, X, y, **kwargs)
        self._temporal_bin_diagnostics_ = diagnostics
        return diagnostics

    def temporal_variable_summary(
        self,
        X: pd.DataFrame | None = None,
        y: pd.Series | None = None,
        *,
        diagnostics: pd.DataFrame | None = None,
        time_col: str | None = None,
        dataset_name: str | None = None,
        min_bin_count: int = 30,
        min_bin_share: float = 0.05,
        min_time_coverage: float = 0.75,
        event_rate_std_threshold: float = 0.05,
        woe_std_threshold: float = 0.5,
        bin_share_std_threshold: float = 0.05,
    ) -> pd.DataFrame:
        if diagnostics is None:
            if X is None or y is None or time_col is None:
                raise ValueError("Provide diagnostics or (X, y, time_col).")
            diagnostics = self.temporal_bin_diagnostics(
                X,
                y,
                time_col=time_col,
                dataset_name=dataset_name,
                min_bin_count=min_bin_count,
                min_bin_share=min_bin_share,
                min_time_coverage=min_time_coverage,
            )
        summary = summarize_temporal_variable_stability(
            diagnostics,
            time_col=time_col,
            event_rate_std_threshold=event_rate_std_threshold,
            woe_std_threshold=woe_std_threshold,
            bin_share_std_threshold=bin_share_std_threshold,
        )
        self._temporal_variable_summary_ = summary
        return summary

    def variable_audit_report(self, X: pd.DataFrame | None = None, y: pd.Series | None = None, **kwargs: Any) -> pd.DataFrame:
        report = build_variable_audit_report(self, X, y, **kwargs)
        self._variable_audit_report_ = report
        return report


def build_riskbands_candidate_configs() -> list[dict[str, Any]]:
    return [
        {
            "name": "riskbands_static",
            "strategy": "supervised",
            "max_bins": 6,
            "min_event_rate_diff": 0.00,
            "check_stability": False,
        },
        {
            "name": "riskbands_static_compact",
            "strategy": "supervised",
            "max_bins": 4,
            "min_event_rate_diff": 0.00,
            "check_stability": False,
        },
        {
            "name": "riskbands_temporal_quantile",
            "strategy": "unsupervised",
            "method": "quantile",
            "n_bins": 3,
            "check_stability": True,
        },
        {
            "name": "riskbands_temporal_uniform",
            "strategy": "unsupervised",
            "method": "uniform",
            "n_bins": 4,
            "check_stability": True,
        },
        {
            "name": "riskbands_balanced_guard",
            "strategy": "supervised",
            "max_bins": 4,
            "min_event_rate_diff": 0.04,
            "check_stability": True,
            "monotonic": "ascending",
        },
    ]


def _evaluate_external_baseline(
    X: pd.DataFrame,
    y: pd.Series,
    *,
    time_col: str,
    dataset_name: str = "benchmark",
    objective_kwargs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    baseline = DirectOptimalBinningBaseline(variable="bureau_score", max_bins=6)
    baseline.fit(X[["bureau_score"]], y)
    pivot = baseline.stability_over_time(X, y, time_col=time_col)
    diagnostics = baseline.temporal_bin_diagnostics(X, y, time_col=time_col, dataset_name=dataset_name)
    summary = baseline.temporal_variable_summary(diagnostics=diagnostics, time_col=time_col)
    audit = baseline.variable_audit_report(
        X,
        y,
        time_col=time_col,
        dataset_name=dataset_name,
        diagnostics=diagnostics,
        summary=summary,
        candidate_name="optimal_binning_pure",
        objective_kwargs=objective_kwargs,
    )
    return {
        "label": "OptimalBinning puro",
        "candidate_name": "optimal_binning_pure",
        "model": baseline,
        "pivot": pivot,
        "diagnostics": diagnostics,
        "summary": summary,
        "audit": audit,
    }


def _approach_row(
    report_row: pd.Series,
    *,
    approach_label: str,
    benchmark_role: str,
    selected_by_riskbands: bool,
) -> dict[str, Any]:
    row = report_row.to_dict()
    row["approach_label"] = approach_label
    row["benchmark_role"] = benchmark_role
    row["selected_by_riskbands"] = selected_by_riskbands
    row["total_penalty"] = float(row.get("objective_total_penalty", np.nan))
    return row


def _infer_numeric_cut_edges_from_model(
    binner: Any,
    X: pd.DataFrame,
    *,
    variable: str = "bureau_score",
) -> list[float]:
    raw_labels = []
    if getattr(binner, "bin_summary", None) is not None:
        raw_labels = binner.bin_summary.loc[
            binner.bin_summary["variable"] == variable,
            "bin",
        ].astype(str).tolist()
    edges = extract_numeric_cut_edges(raw_labels)
    if edges:
        return edges

    transformed = binner.transform(X[[variable]])
    bin_values = transformed if isinstance(transformed, pd.Series) else transformed[variable]
    frame = (
        pd.DataFrame({variable: X[variable].astype(float), "bin": bin_values})
        .dropna()
        .groupby("bin")[variable]
        .agg(min_value="min", max_value="max")
        .sort_values("min_value")
        .reset_index(drop=True)
    )
    inferred = []
    for idx in range(len(frame) - 1):
        left = float(frame.iloc[idx]["max_value"])
        right = float(frame.iloc[idx + 1]["min_value"])
        if np.isfinite(left) and np.isfinite(right):
            inferred.append((left + right) / 2.0)
    return inferred


def _build_benchmark_candidate_views(
    comparator: BinComparator,
    X: pd.DataFrame,
    y: pd.Series,
    *,
    time_col: str,
    dataset_name: str,
    objective_kwargs: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, dict[str, Any]]]:
    candidate_rows = []
    candidate_views: dict[str, dict[str, Any]] = {}

    for result in comparator.results_:
        candidate_name = str(result["name"])
        binner = result["binner"]
        diagnostics = binner.temporal_bin_diagnostics(
            X,
            y,
            time_col=time_col,
            dataset_name=dataset_name,
        )
        summary = binner.temporal_variable_summary(diagnostics=diagnostics, time_col=time_col)
        audit = binner.variable_audit_report(
            X,
            y,
            time_col=time_col,
            dataset_name=dataset_name,
            diagnostics=diagnostics,
            summary=summary,
            candidate_name=candidate_name,
            objective_kwargs=objective_kwargs,
        )
        candidate_views[candidate_name] = {
            "candidate_name": candidate_name,
            "model": binner,
            "diagnostics": diagnostics,
            "summary": summary,
            "audit": audit,
        }
        candidate_rows.append(audit)

    candidate_audit = pd.concat(candidate_rows, ignore_index=True)
    candidate_profiles = build_candidate_profile_report(candidate_audit)
    winner_summary = build_candidate_winner_report(candidate_profiles)
    return candidate_audit, candidate_profiles, winner_summary, candidate_views


def _build_approach_board(
    *,
    external_audit: pd.DataFrame,
    candidate_audit: pd.DataFrame,
    winner_summary: pd.DataFrame,
) -> pd.DataFrame:
    winner = winner_summary.iloc[0]
    selected_candidate = str(winner["selected_candidate"])
    static_row = candidate_audit.loc[candidate_audit["candidate_name"] == "riskbands_static"].iloc[0]
    selected_row = candidate_audit.loc[candidate_audit["candidate_name"] == selected_candidate].iloc[0]
    external_row = external_audit.iloc[0]

    board = pd.DataFrame(
        [
            _approach_row(
                external_row,
                approach_label="OptimalBinning puro",
                benchmark_role="external_baseline",
                selected_by_riskbands=False,
            ),
            _approach_row(
                static_row,
                approach_label="RiskBands estatico",
                benchmark_role="internal_static",
                selected_by_riskbands=False,
            ),
            _approach_row(
                selected_row,
                approach_label="RiskBands selecionado",
                benchmark_role="riskbands_selected",
                selected_by_riskbands=True,
            ),
        ]
    )
    order = {"external_baseline": 0, "internal_static": 1, "riskbands_selected": 2}
    board["sort_key"] = board["benchmark_role"].map(order)
    return board.sort_values("sort_key").drop(columns="sort_key").reset_index(drop=True)


def _build_scenario_takeaways(
    scenario_name: str,
    board: pd.DataFrame,
    winner_summary: pd.DataFrame,
) -> list[str]:
    winner = winner_summary.iloc[0]
    external = board.loc[board["benchmark_role"] == "external_baseline"].iloc[0]
    static = board.loc[board["benchmark_role"] == "internal_static"].iloc[0]
    selected = board.loc[board["benchmark_role"] == "riskbands_selected"].iloc[0]

    takeaways = [f"Cenario `{scenario_name}`: o candidato final do RiskBands foi `{winner['selected_candidate']}`."]
    if winner["selected_candidate"] == "riskbands_static":
        takeaways.append(
            "Neste caso o RiskBands concordou com a leitura estatica: a auditoria temporal nao encontrou ganho suficiente para justificar abandonar o candidato mais discriminante."
        )
    else:
        takeaways.append(
            "Aqui o RiskBands nao ficou preso ao IV bruto: ele preferiu um candidato com melhor equilibrio entre discriminacao, cobertura e estabilidade temporal."
        )
    if winner["best_temporal_candidate"] != winner["selected_candidate"]:
        takeaways.append(
            f"O lider puramente temporal foi `{winner['best_temporal_candidate']}`, mas o score balanceado final permaneceu com `{winner['selected_candidate']}` por um trade-off mais favoravel entre estabilidade e discriminacao."
        )
    if float(external["iv"]) >= float(selected["iv"]) and float(selected["temporal_score"]) > float(external["temporal_score"]):
        takeaways.append(
            "A baseline externa de OptimalBinning manteve IV competitivo, mas perdeu em score temporal, sugerindo fragilidade relevante para uso em credito."
        )
    if int(selected["ranking_reversal_period_count"]) < int(static["ranking_reversal_period_count"]):
        takeaways.append(
            "O candidato selecionado reduziu reversoes de ranking frente ao baseline estatico interno, melhorando a defendibilidade entre safras."
        )
    if float(selected["coverage_ratio_min"]) > float(static["coverage_ratio_min"]):
        takeaways.append(
            "O ganho do RiskBands veio acompanhado de melhor cobertura minima, evitando bins que somem ou ficam rasos demais em algumas vintages."
        )
    if float(selected["iv"]) < float(static["iv"]):
        takeaways.append(
            "O trade-off observado foi claro: o candidato final abriu mao de um pouco de discriminacao estatica para ganhar robustez temporal."
        )
    takeaways.append(f"Racional do vencedor: {selected['rationale_summary']}")
    return takeaways


def _build_scenario_summary(results_by_scenario: dict[str, dict[str, Any]]) -> pd.DataFrame:
    records = []
    for scenario_name, result in results_by_scenario.items():
        board = result["approach_board"].set_index("benchmark_role")
        winner = result["winner_summary"].iloc[0]
        records.append(
            {
                "scenario": scenario_name,
                "scenario_title": result["scenario_spec"].title,
                "best_temporal_candidate": winner["best_temporal_candidate"],
                "best_balanced_candidate": winner["best_balanced_candidate"],
                "selected_candidate": winner["selected_candidate"],
                "selected_equals_static": winner["selected_candidate"] == "riskbands_static",
                "external_iv": float(board.loc["external_baseline", "iv"]),
                "static_iv": float(board.loc["internal_static", "iv"]),
                "selected_iv": float(board.loc["riskbands_selected", "iv"]),
                "external_temporal_score": float(board.loc["external_baseline", "temporal_score"]),
                "static_temporal_score": float(board.loc["internal_static", "temporal_score"]),
                "selected_temporal_score": float(board.loc["riskbands_selected", "temporal_score"]),
                "external_objective_score": float(board.loc["external_baseline", "objective_score"]),
                "static_objective_score": float(board.loc["internal_static", "objective_score"]),
                "selected_objective_score": float(board.loc["riskbands_selected", "objective_score"]),
                "selected_advantage_vs_static": float(board.loc["riskbands_selected", "objective_score"]) - float(board.loc["internal_static", "objective_score"]),
                "selected_advantage_vs_external": float(board.loc["riskbands_selected", "objective_score"]) - float(board.loc["external_baseline", "objective_score"]),
                "selected_ranking_reversals": int(board.loc["riskbands_selected", "ranking_reversal_period_count"]),
                "selected_basis": winner["selected_basis"],
                "selected_alert_flags": str(board.loc["riskbands_selected", "alert_flags"]),
            }
        )
    return pd.DataFrame(records).sort_values("scenario").reset_index(drop=True)


def build_benchmark_visuals(result: dict[str, Any]) -> dict[str, Any]:
    approach_board = result["approach_board"]
    selected_row = approach_board.loc[approach_board["benchmark_role"] == "riskbands_selected"].iloc[0]
    cut_edges = _infer_numeric_cut_edges_from_model(
        result["selected"]["model"],
        result["X"],
        variable="bureau_score",
    )
    return {
        "benchmark_board": plot_benchmark_board(
            approach_board,
            title=f"{result['scenario_spec'].title}: approach board",
        ),
        "metric_comparison": plot_metric_bars(
            approach_board,
            title=f"{result['scenario_spec'].title}: static vs temporal trade-offs",
            metrics=[
                {"column": "iv", "label": "IV"},
                {"column": "temporal_score", "label": "Temporal score"},
                {"column": "total_penalty", "label": "Total penalty"},
                {"column": "coverage_ratio_min", "label": "Coverage min", "percent": True},
            ],
        ),
        "event_rate_curves": plot_event_rate_curves_by_approach(
            {
                "OptimalBinning puro": result["external"]["diagnostics"],
                "RiskBands estatico": result["static"]["diagnostics"],
                "RiskBands selecionado": result["selected"]["diagnostics"],
            },
            time_col="month",
            title=f"{result['scenario_spec'].title}: event rate por bin ao longo do tempo",
        ),
        "selected_heatmap": plot_event_rate_heatmap(
            result["selected"]["diagnostics"],
            time_col="month",
            title=f"{result['scenario_spec'].title}: heatmap do candidato selecionado",
        ),
        "aggregate_vs_vintage": plot_aggregate_vs_vintage_gap(
            result["external"]["diagnostics"],
            time_col="month",
            title=f"{result['scenario_spec'].title}: agregado vs vintages (baseline externa)",
        ),
        "penalty_breakdown": plot_penalty_breakdown(
            approach_board,
            title=f"{result['scenario_spec'].title}: penalizacoes por abordagem",
        ),
        "score_distribution": plot_score_distribution_with_cutpoints(
            result["panel"],
            value_col="bureau_score",
            time_col="month",
            bin_labels=str(selected_row["cut_summary"]).split(" | "),
            cut_edges=cut_edges,
            title=f"{result['scenario_spec'].title}: distribuicao do score com cortes selecionados",
        ),
        "sampling_preview": plot_sampling_preview(
            result["sampling_preview"],
            title=f"{result['scenario_spec'].title}: preview opcional de sampling por safra",
        ),
    }


def run_benchmark_scenario(
    *,
    scenario: str = ANCHOR_SCENARIO,
    seed: int = 73,
    samples_per_period: int = 220,
) -> dict[str, Any]:
    panel = build_credit_benchmark_panel(
        scenario=scenario,
        seed=seed,
        samples_per_period=samples_per_period,
    )
    X = panel[["bureau_score", "month"]].reset_index(drop=True)
    y = panel["target"].reset_index(drop=True)

    external = _evaluate_external_baseline(
        X,
        y,
        time_col="month",
        objective_kwargs=BENCHMARK_OBJECTIVE_KWARGS,
    )
    comparator = BinComparator(build_riskbands_candidate_configs(), time_col="month")
    fit_summary = comparator.fit_compare(X, y)
    candidate_audit, candidate_profiles, winner_summary, candidate_views = _build_benchmark_candidate_views(
        comparator,
        X,
        y,
        time_col="month",
        dataset_name="benchmark",
        objective_kwargs=BENCHMARK_OBJECTIVE_KWARGS,
    )

    selected_candidate = str(winner_summary.iloc[0]["selected_candidate"])

    approach_board = _build_approach_board(
        external_audit=external["audit"],
        candidate_audit=candidate_audit,
        winner_summary=winner_summary,
    )
    leaderboard = pd.concat([external["audit"], candidate_audit], ignore_index=True).sort_values(
        ["objective_score", "temporal_score", "iv"],
        ascending=False,
    ).reset_index(drop=True)

    return {
        "scenario_name": scenario,
        "scenario_spec": SCENARIOS[scenario],
        "panel": panel,
        "X": X,
        "y": y,
        "fit_summary": fit_summary,
        "candidate_audit": candidate_audit,
        "candidate_profiles": candidate_profiles,
        "winner_summary": winner_summary,
        "leaderboard": leaderboard,
        "approach_board": approach_board,
        "external": external,
        "static": candidate_views["riskbands_static"],
        "selected": candidate_views[selected_candidate],
        "candidate_views": candidate_views,
        "sampling_preview": build_sampling_preview(panel, seed=seed),
        "credit_takeaways": _build_scenario_takeaways(scenario, approach_board, winner_summary),
    }


def run_benchmark_suite(
    *,
    scenarios: tuple[str, ...] | list[str] = DEFAULT_SCENARIOS,
    seed: int = 73,
    samples_per_period: int = 220,
) -> dict[str, Any]:
    results_by_scenario = {
        scenario: run_benchmark_scenario(
            scenario=scenario,
            seed=seed,
            samples_per_period=samples_per_period,
        )
        for scenario in scenarios
    }
    return {
        "scenario_summary": _build_scenario_summary(results_by_scenario),
        "scenarios": results_by_scenario,
    }


def _print_scenario_report(result: dict[str, Any]) -> None:
    print(f"\n== {result['scenario_spec'].title} ==")
    print(result["scenario_spec"].description)
    print("\nApproach board:")
    print(
        result["approach_board"][
            [
                "approach_label",
                "candidate_name",
                "iv",
                "temporal_score",
                "objective_score",
                "total_penalty",
                "coverage_ratio_min",
                "ranking_reversal_period_count",
                "alert_flags",
            ]
        ]
    )
    print("\nWinner summary:")
    print(result["winner_summary"])
    print("\nTakeaways:")
    for takeaway in result["credit_takeaways"]:
        print(f"- {takeaway}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the premium PD vintage benchmark.")
    parser.add_argument("--scenario", default=ANCHOR_SCENARIO, choices=sorted(SCENARIOS))
    parser.add_argument("--all-scenarios", action="store_true")
    parser.add_argument("--samples-per-period", type=int, default=220)
    parser.add_argument("--export-html-dir", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    scenarios = DEFAULT_SCENARIOS if args.all_scenarios else (args.scenario,)
    suite = run_benchmark_suite(
        scenarios=scenarios,
        samples_per_period=args.samples_per_period,
    )
    print("== Scenario summary ==")
    print(suite["scenario_summary"])

    if args.all_scenarios:
        for result in suite["scenarios"].values():
            _print_scenario_report(result)
        if args.export_html_dir is not None:
            written = []
            for scenario_name, result in suite["scenarios"].items():
                written.extend(
                    export_figure_pack(
                        build_benchmark_visuals(result),
                        args.export_html_dir,
                        prefix=scenario_name,
                    )
                )
            print("\nExported figures:")
            for item in written:
                print(f"- {item}")
    else:
        anchor = suite["scenarios"][args.scenario]
        _print_scenario_report(anchor)
        if args.export_html_dir is not None:
            written = export_figure_pack(
                build_benchmark_visuals(anchor),
                args.export_html_dir,
                prefix=args.scenario,
            )
            print("\nExported figures:")
            for item in written:
                print(f"- {item}")


if __name__ == "__main__":
    main()
