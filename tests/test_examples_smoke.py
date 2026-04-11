from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _load_example_module(relative_path: str):
    root = Path(__file__).resolve().parents[1]
    path = root / relative_path
    spec = spec_from_file_location(path.stem, path)
    module = module_from_spec(spec)
    assert spec.loader is not None
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
    assert winner_row["best_balanced_candidate"] == "static_compact"
    assert winner_row["selected_candidate"] == "static_compact"

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
        "audit_report",
        "ks_over_time",
        "temporal_separability",
    } <= set(results)
    assert not results["pivot"].empty
    assert not results["diagnostics"].empty
    assert not results["summary"].empty
    assert not results["audit_report"].empty


