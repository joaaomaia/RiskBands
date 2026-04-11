# Examples

## Start Here

- `examples/temporal_stability_example.py`
  Quickstart for the temporal core: `fit`, `stability_over_time`, diagnostics and audit report.

- `examples/pd_vintage_champion_challenger.py`
  Anchor example for credit risk / PD with multiple vintages. Shows champion/challenger between static, temporal and balanced candidate profiles.

## How To Read Them

- Start with `temporal_stability_example.py` if you want to understand the mechanics of the API.
- Go to `pd_vintage_champion_challenger.py` if your main question is:
  "How can a binning that looks stronger in train lose to a more robust alternative over time?"

Both examples stay inside the NASABinning scope:
- no end-to-end PD pipeline
- no model monitoring layer
- only binning, temporal stability and auditable candidate comparison
