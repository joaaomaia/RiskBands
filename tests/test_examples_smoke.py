import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pandas as pd


def _load_example_module(relative_path: str):
    root = Path(__file__).resolve().parents[1]
    path = root / relative_path
    spec = spec_from_file_location(path.stem, path)
    module = module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_pd_vintage_champion_challenger_example_flow_smoke():
    module = _load_example_module(
        "examples/pd_vintage_champion_challenger/pd_vintage_champion_challenger.py"
    )

    results = module.run_pd_vintage_champion_challenger_demo()

    assert {
        "fit_summary",
        "candidate_audit",
        "candidate_profiles",
        "winner_summary",
        "champion_board",
        "selected_audit",
        "sampling_preview",
        "credit_takeaways",
    } <= set(results)

    winner_row = results["winner_summary"].iloc[0]
    assert winner_row["best_static_candidate"] == "static_aggressive"
    assert winner_row["best_temporal_candidate"] == "temporal_quantile_3"
    assert winner_row["best_balanced_candidate"] == "temporal_quantile_3"
    assert winner_row["selected_candidate"] == "temporal_quantile_3"

    champion_board = results["champion_board"]
    assert set(champion_board["profile"]) == {
        "static_champion",
        "temporal_champion",
        "balanced_champion",
    }
    assert champion_board["selected_final_candidate"].sum() == 1
    assert not results["sampling_preview"].empty
    assert len(results["credit_takeaways"]) >= 3


def test_temporal_stability_example_flow_smoke():
    module = _load_example_module(
        "examples/temporal_stability/temporal_stability_example.py"
    )

    results = module.run_temporal_stability_demo(seed=1, n=320)

    assert {
        "pivot",
        "diagnostics",
        "summary",
        "score_table",
        "audit_table",
        "audit_report",
        "ks_over_time",
        "temporal_separability",
        "bad_rate_over_time",
        "bad_rate_heatmap",
        "bin_share_over_time",
        "score_components",
        "exported_paths",
    } <= set(results)
    assert not results["pivot"].empty
    assert not results["diagnostics"].empty
    assert not results["summary"].empty
    assert not results["audit_report"].empty


def test_pd_vintage_benchmark_example_flow_smoke():
    module = _load_example_module(
        "examples/pd_vintage_benchmark/pd_vintage_benchmark.py"
    )

    suite = module.run_benchmark_suite(samples_per_period=180)

    assert {"scenario_summary", "scenarios"} <= set(suite)
    summary = suite["scenario_summary"].set_index("scenario")
    assert set(summary.index) == {
        "stable_credit",
        "temporal_reversal",
        "composition_shift",
    }
    assert summary.loc["stable_credit", "selected_candidate"] == "riskbands_temporal_uniform"
    assert summary.loc["temporal_reversal", "selected_candidate"] == "riskbands_temporal_quantile"
    assert summary.loc["composition_shift", "selected_candidate"] == "riskbands_temporal_quantile"

    anchor = suite["scenarios"]["temporal_reversal"]
    assert {
        "approach_board",
        "candidate_profiles",
        "winner_summary",
        "credit_takeaways",
        "sampling_preview",
    } <= set(anchor)
    assert {
        "external_baseline",
        "internal_static",
        "riskbands_selected",
    } == set(anchor["approach_board"]["benchmark_role"])
    assert not anchor["sampling_preview"].empty
    assert len(anchor["credit_takeaways"]) >= 3

    figures = module.build_benchmark_visuals(anchor)
    assert {
        "benchmark_board",
        "metric_comparison",
        "event_rate_curves",
        "selected_heatmap",
        "aggregate_vs_vintage",
        "penalty_breakdown",
        "score_distribution",
        "sampling_preview",
    } <= set(figures)


def test_stable_score_example_flow_smoke():
    module = _load_example_module(
        "examples/stable_score/stable_score_demo.py"
    )

    results = module.run_stable_score_demo(seed=11)

    assert {
        "legacy_fit_summary",
        "legacy_candidate_audit",
        "legacy_winner_summary",
        "stable_fit_summary",
        "stable_candidate_audit",
        "stable_winner_summary",
        "selection_comparison",
        "baseline_note",
    } <= set(results)
    assert not results["legacy_candidate_audit"].empty
    assert not results["stable_candidate_audit"].empty
    assert len(results["baseline_note"]) > 20


def test_missing_policy_pandas_example_flow_smoke():
    module = _load_example_module(
        "examples/missing_policy/missing_policy_pandas_demo.py"
    )

    results = module.run_pandas_missing_policy_demo()

    assert {
        "dataset",
        "standard",
        "separate_bin",
        "merge_dataset",
        "merge_nearest_event_rate",
        "merge_nearest_woe",
        "forbid_fit_error",
        "forbid_transform_error",
        "bundle_summary",
    } <= set(results)
    assert not results["standard"]["missing_decision_log"].empty
    assert not results["separate_bin"]["missing_profile"].empty
    assert set(results["separate_bin"]["transformed_head"]["rating"].astype(str)) >= {"Missing"}
    assert "missing_policy='forbid'" in results["forbid_fit_error"]
    assert results["bundle_summary"]["missing_policy"] == "separate_bin"

    for key, criterion in [
        ("merge_nearest_event_rate", "nearest_event_rate"),
        ("merge_nearest_woe", "nearest_woe"),
    ]:
        merge = results[key]
        assert merge["missing_decision_log"].iloc[0]["action"] == "missing_merged"
        assert merge["missing_decision_log"].iloc[0]["missing_merge_criterion"] == criterion
        assert not merge["missing_merge_candidates"].empty
        assert merge["missing_merge_map"]["score"] == merge["missing_decision_log"].iloc[0]["selected_bin_label"]
        assert merge["transformed"].loc[0, "score"] == merge["missing_decision_log"].iloc[0]["selected_bin_label"]
        assert merge["transformed"].loc[0, "score"] != "Missing"
        assert pd.api.types.is_numeric_dtype(merge["transformed_woe"]["score"])
        assert merge["bundle_summary"]["missing_policy"] == "merge"
        assert merge["bundle_summary"]["missing_merge_criterion"] == criterion


def test_missing_policy_pyspark_example_optional_guard(monkeypatch):
    module = _load_example_module(
        "examples/missing_policy/missing_policy_pyspark_demo.py"
    )
    monkeypatch.setattr(module, "_spark_imports", lambda: (None, None))

    results = module.run_pyspark_missing_policy_demo()

    assert results == {"skipped": True, "reason": "pyspark is not installed"}
