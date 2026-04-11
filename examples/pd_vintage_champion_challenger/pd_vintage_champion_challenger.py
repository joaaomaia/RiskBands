"""Anchor example for PD binning with vintages and champion/challenger flow.

This example stays strictly inside the RiskBands scope:
- no end-to-end PD model training
- no portfolio monitoring layer
- only binning, temporal stability, and candidate comparison
"""

from __future__ import annotations

import logging
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW_MATERIAL = ROOT / "research" / "raw_material"
for candidate_path in (ROOT, RAW_MATERIAL):
    if str(candidate_path) not in sys.path:
        sys.path.insert(0, str(candidate_path))

from credit_data_sampler import TargetSampler
from credit_data_synthesizer import build_riskbands_pd_example_frame
from riskbands.compare import BinComparator


def make_pd_vintage_dataset(
    seed: int = 73,
    n_per_period: int = 180,
) -> tuple[pd.DataFrame, pd.Series]:
    """Create a small PD-style frame with vintages using the raw-material helpers."""
    panel = build_riskbands_pd_example_frame(
        random_seed=seed,
        samples_per_period=n_per_period,
    )
    X = panel[["bureau_score", "month"]].reset_index(drop=True)
    y = panel["target"].reset_index(drop=True)
    return X, y


def build_sampling_preview(
    seed: int = 73,
    n_per_period: int = 180,
    target_ratio: float = 0.30,
) -> pd.DataFrame:
    """Show how the sampler can rebalance vintages without changing the core example."""
    panel = build_riskbands_pd_example_frame(
        random_seed=seed,
        samples_per_period=n_per_period,
    )
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

    preview = pd.DataFrame(
        {
            "month": raw_by_month.index,
            "raw_target_rate": raw_by_month["mean"].values,
            "sampled_target_rate": sampled_by_month["mean"].reindex(raw_by_month.index).values,
            "raw_count": raw_by_month["size"].values,
            "sampled_count": sampled_by_month["size"].reindex(raw_by_month.index).values,
        }
    )
    return preview.reset_index(drop=True)


def build_candidate_configs() -> list[dict]:
    """Small pool of candidate philosophies for champion/challenger review."""
    return [
        {
            "name": "static_aggressive",
            "strategy": "supervised",
            "max_bins": 8,
            "min_event_rate_diff": 0.00,
            "check_stability": False,
        },
        {
            "name": "static_compact",
            "strategy": "supervised",
            "max_bins": 5,
            "min_event_rate_diff": 0.00,
            "check_stability": False,
        },
        {
            "name": "temporal_quantile_3",
            "strategy": "unsupervised",
            "method": "quantile",
            "n_bins": 3,
            "check_stability": True,
        },
        {
            "name": "temporal_uniform_4",
            "strategy": "unsupervised",
            "method": "uniform",
            "n_bins": 4,
            "check_stability": True,
        },
        {
            "name": "balanced_monotonic",
            "strategy": "supervised",
            "max_bins": 4,
            "min_event_rate_diff": 0.03,
            "check_stability": True,
            "monotonic": "ascending",
        },
        {
            "name": "balanced_stability_guard",
            "strategy": "supervised",
            "max_bins": 4,
            "min_event_rate_diff": 0.05,
            "check_stability": True,
        },
    ]


def build_champion_challenger_board(
    candidate_audit: pd.DataFrame,
    winner_summary: pd.DataFrame,
) -> pd.DataFrame:
    """Build a concise board for static, temporal and balanced champions."""
    winner_row = winner_summary.iloc[0]
    profile_map = [
        ("static_champion", "best_static_candidate", "Maior forca em discriminacao estatica."),
        ("temporal_champion", "best_temporal_candidate", "Melhor comportamento no perfil temporal agregado."),
        (
            "balanced_champion",
            "best_balanced_candidate",
            "Melhor equilibrio entre poder de separacao e robustez temporal.",
        ),
    ]

    records = []
    for profile_name, winner_col, interpretation in profile_map:
        candidate_name = winner_row[winner_col]
        candidate_row = (
            candidate_audit.loc[candidate_audit["candidate_name"] == candidate_name]
            .sort_values("variable")
            .iloc[0]
        )
        records.append(
            {
                "profile": profile_name,
                "candidate_name": candidate_name,
                "selected_final_candidate": candidate_name == winner_row["selected_candidate"],
                "iv": candidate_row["iv"],
                "ks": candidate_row["ks"],
                "temporal_score": candidate_row["temporal_score"],
                "objective_score": candidate_row["objective_score"],
                "rare_bin_count": candidate_row["rare_bin_count"],
                "coverage_ratio_min": candidate_row["coverage_ratio_min"],
                "ranking_reversal_period_count": candidate_row["ranking_reversal_period_count"],
                "alert_flags": candidate_row["alert_flags"],
                "key_penalties": candidate_row["key_penalties"],
                "rationale_summary": candidate_row["rationale_summary"],
                "credit_interpretation": interpretation,
            }
        )

    return pd.DataFrame(records)


def build_credit_takeaways(
    champion_board: pd.DataFrame,
    winner_summary: pd.DataFrame,
) -> list[str]:
    """Create short, credit-oriented takeaways for the example output."""
    winner_row = winner_summary.iloc[0]
    balanced_row = champion_board.loc[champion_board["profile"] == "balanced_champion"].iloc[0]
    static_row = champion_board.loc[champion_board["profile"] == "static_champion"].iloc[0]
    temporal_row = champion_board.loc[champion_board["profile"] == "temporal_champion"].iloc[0]

    return [
        (
            f"O campeao estatico foi `{static_row['candidate_name']}`, olhando primeiro para "
            "poder de separacao."
        ),
        (
            f"O campeao temporal foi `{temporal_row['candidate_name']}`, olhando primeiro para "
            "o perfil temporal agregado e a fragilidade estrutural."
        ),
        (
            f"O selecionado final foi `{winner_row['selected_candidate']}`, que tambem apareceu "
            "como campeao equilibrado neste fluxo."
        ),
        (
            "Em credito, isso ajuda a mostrar que a escolha final nao depende so de IV: "
            "cobertura, penalizacoes, instabilidade e reversoes tambem entram na leitura."
        ),
        (
            f"Os principais sinais do vencedor foram: {balanced_row['rationale_summary']}"
        ),
    ]


def run_pd_vintage_champion_challenger_demo(
    seed: int = 73,
    n_per_period: int = 180,
) -> dict[str, pd.DataFrame | list[str]]:
    """Run the anchor example and return all intermediate tables."""
    X, y = make_pd_vintage_dataset(seed=seed, n_per_period=n_per_period)
    sampling_preview = build_sampling_preview(seed=seed, n_per_period=n_per_period)
    comparator = BinComparator(build_candidate_configs(), time_col="month")
    summary = comparator.fit_compare(X, y)
    candidate_audit = comparator.candidate_audit_report()
    candidate_profiles = comparator.candidate_profile_summary()
    winner_summary = comparator.winner_summary()
    champion_board = build_champion_challenger_board(candidate_audit, winner_summary)
    takeaways = build_credit_takeaways(champion_board, winner_summary)

    selected_candidate = winner_summary.iloc[0]["selected_candidate"]
    selected_audit = (
        candidate_audit.loc[candidate_audit["candidate_name"] == selected_candidate]
        .sort_values("variable")
        .reset_index(drop=True)
    )

    return {
        "X": X,
        "y": y,
        "fit_summary": summary,
        "candidate_audit": candidate_audit,
        "candidate_profiles": candidate_profiles,
        "winner_summary": winner_summary,
        "champion_board": champion_board,
        "selected_audit": selected_audit,
        "sampling_preview": sampling_preview,
        "credit_takeaways": takeaways,
    }


def main() -> None:
    results = run_pd_vintage_champion_challenger_demo()

    print("== Fit summary ==")
    print(
        results["fit_summary"][
            ["iv", "objective_score", "temporal_score", "total_penalty", "alert_flags"]
        ]
    )
    print("\n== Champion / challenger board ==")
    print(
        results["champion_board"][
            [
                "profile",
                "candidate_name",
                "selected_final_candidate",
                "iv",
                "temporal_score",
                "objective_score",
                "key_penalties",
            ]
        ]
    )
    print("\n== Winner summary ==")
    print(results["winner_summary"])
    print("\n== Optional sampling preview ==")
    print(results["sampling_preview"])
    print("\n== Selected candidate audit ==")
    print(
        results["selected_audit"][
            [
                "candidate_name",
                "variable",
                "iv",
                "ks",
                "temporal_score",
                "coverage_ratio_min",
                "rare_bin_count",
                "rationale_summary",
            ]
        ]
    )
    print("\n== Credit takeaways ==")
    for line in results["credit_takeaways"]:
        print(f"- {line}")


if __name__ == "__main__":
    main()
