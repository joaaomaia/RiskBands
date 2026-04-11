from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _load_example_module(filename: str):
    root = Path(__file__).resolve().parents[1]
    path = root / "examples" / filename
    spec = spec_from_file_location(path.stem, path)
    module = module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_pd_vintage_champion_challenger_example_flow_smoke():
    module = _load_example_module("pd_vintage_champion_challenger.py")

    results = module.run_pd_vintage_champion_challenger_demo()

    assert {
        "fit_summary",
        "candidate_audit",
        "candidate_profiles",
        "winner_summary",
        "champion_board",
        "selected_audit",
        "credit_takeaways",
    } <= set(results)

    winner_row = results["winner_summary"].iloc[0]
    assert winner_row["best_static_candidate"] == "static_aggressive"
    assert winner_row["best_temporal_candidate"] == "temporal_quantile_3"
    assert winner_row["best_balanced_candidate"] == "balanced_monotonic"
    assert winner_row["selected_candidate"] == "balanced_monotonic"

    champion_board = results["champion_board"]
    assert set(champion_board["profile"]) == {
        "static_champion",
        "temporal_champion",
        "balanced_champion",
    }
    assert champion_board["selected_final_candidate"].sum() == 1
    assert len(results["credit_takeaways"]) >= 3
