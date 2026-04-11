# Examples

## Start Here

- `examples/temporal_stability/temporal_stability_example.py`
  Quickstart for the temporal core: `fit`, `stability_over_time`, diagnostics and audit report.

- `examples/temporal_stability/temporal_stability_example.ipynb`
  Notebook counterpart for a more guided walk through the same flow.

- `examples/pd_vintage_champion_challenger/pd_vintage_champion_challenger.py`
  Anchor example for credit risk / PD with multiple vintages. Shows champion/challenger between static, temporal and balanced candidate profiles.

- `examples/pd_vintage_champion_challenger/pd_vintage_champion_challenger.ipynb`
  More didactic notebook version of the anchor PD example, with narrative focused on credit decisions.

## How To Read Them

- Start with `temporal_stability/` if you want to understand the mechanics of the API before going into credit-specific trade-offs.
- Go to `pd_vintage_champion_challenger/` if your main question is:
  "How can a binning that looks stronger in train lose to a more robust alternative over time?"

## Why The Examples Matter

The examples are organized by folder so a new user can quickly choose between:

- a temporal quickstart
- a PD/vintage champion-challenger flow
- a Python script for reproducible execution
- a notebook for a more guided and explanatory read

Both flagship examples stay inside the NASABinning scope:

- no end-to-end PD pipeline
- no model monitoring layer
- only binning, temporal stability, candidate comparison and auditable rationale

The anchor PD example also reuses the synthetic credit helpers under `research/raw_material/`:

- `credit_data_synthesizer.py` for the vintage panel
- `credit_data_sampler.py` for an optional sampling preview
