# Examples

## Start Here

- `examples/pd_vintage_benchmark/pd_vintage_benchmark.py`
  Benchmark premium comparando `OptimalBinning` puro, RiskBands estatico e RiskBands balanceado em cenarios de credito com drift temporal.

- `examples/pd_vintage_benchmark/pd_vintage_benchmark.ipynb`
  Notebook principal da vitrine metodologica, com board comparativo, heatmaps, curvas por vintage e leitura honesta dos trade-offs.

- `examples/temporal_stability/temporal_stability_example.py`
  Quickstart for the temporal core: `fit`, `stability_over_time`, diagnostics and audit report.

- `examples/temporal_stability/temporal_stability_example.ipynb`
  Notebook counterpart for a more guided walk through the same flow.

- `examples/pd_vintage_champion_challenger/pd_vintage_champion_challenger.py`
  Anchor example for credit risk / PD with multiple vintages. Shows champion/challenger between static, temporal and balanced candidate profiles.

- `examples/pd_vintage_champion_challenger/pd_vintage_champion_challenger.ipynb`
  More didactic notebook version of the anchor PD example, with narrative focused on credit decisions.

## How To Run

- Script: `python examples/pd_vintage_benchmark/pd_vintage_benchmark.py --all-scenarios`
- Script + export HTML: `python examples/pd_vintage_benchmark/pd_vintage_benchmark.py --scenario temporal_reversal --export-html-dir benchmark_html`
- Script: `python examples/temporal_stability/temporal_stability_example.py`
- Script: `python examples/pd_vintage_champion_challenger/pd_vintage_champion_challenger.py`
- Notebook: open the `.ipynb` counterpart in Jupyter or VS Code

## How To Read Them

- Comece por `pd_vintage_benchmark/` se a sua pergunta principal for:
  "Por que um binning estatico com IV alto pode ficar fragil no tempo?"
- Start with `temporal_stability/` if you want to understand the mechanics of the API before going into credit-specific trade-offs.
- Go to `pd_vintage_champion_challenger/` if your main question is:
  "How can a binning that looks stronger in train lose to a more robust alternative over time?"

## Why The Examples Matter

The examples are organized by folder so a new user can quickly choose between:

- a temporal quickstart
- a PD/vintage champion-challenger flow
- a Python script for reproducible execution
- a notebook for a more guided and explanatory read

Both flagship examples stay inside the RiskBands scope:

- no end-to-end PD pipeline
- no model monitoring layer
- only binning, temporal stability, candidate comparison and auditable rationale

The premium benchmark adds one extra layer on top of the existing examples:

- explicit external baseline with `OptimalBinning`
- multi-scenario comparison (`stable_credit`, `temporal_reversal`, `composition_shift`)
- reusable Plotly figures for benchmark-style demos

The anchor PD example also reuses the synthetic credit helpers under `research/raw_material/`:

- `credit_data_synthesizer.py` for the vintage panel
- `credit_data_sampler.py` for an optional sampling preview


