---
title: "Examples"
description: "Scripts and notebooks for quickstart, benchmark, audit, and friendly RiskBands API demonstrations."
---

## Start here

### API ergonomics notebook

This is the recommended entry point for learning RiskBands with a workflow that
feels closer to pandas and sklearn.

- [Synthetic notebook with Plotly](https://github.com/joaaomaia/RiskBands/blob/main/examples/riskbands_synthetic_plotly_comparative_demo.ipynb)

This material shows:

- `fit(df, y="target", column="score", time_col="month")`
- `transform(df["score"])`
- `summary()`
- `binning_table()`
- `score_details()`
- `diagnostics()`
- comparison between `standard` and `stable`

### Temporal stability quickstart

This is the shortest entry point to the temporal layer, now with score table,
audit table, and auditable export.

- [Quickstart script](https://github.com/joaaomaia/RiskBands/blob/main/examples/temporal_stability/temporal_stability_example.py)
- [Quickstart notebook](https://github.com/joaaomaia/RiskBands/blob/main/examples/temporal_stability/temporal_stability_example.ipynb)

This flow already shows:

- `score_table()`
- `audit_table()`
- `export_binnings_json(...)`
- `export_bundle(...)`
- `plot_bad_rate_over_time(...)`
- `plot_bad_rate_heatmap(...)`
- `plot_bin_share_over_time(...)`
- `plot_score_components(...)`

### Missing policy with pandas and PySpark

Use these scripts when the main question is how to handle missing values in an
auditable way without opaque imputation.

- [pandas missing policy demo](https://github.com/joaaomaia/RiskBands/blob/main/examples/missing_policy/missing_policy_pandas_demo.py)
- [PySpark missing policy demo](https://github.com/joaaomaia/RiskBands/blob/main/examples/missing_policy/missing_policy_pyspark_demo.py)

They show:

- `missing_policy="standard"`
- `missing_policy="separate_bin"`
- `missing_policy="forbid"`
- `missing_profile_`
- `missing_decision_log_`
- bundle fields for missing policy
- optional guard for PySpark

### PD vintage champion/challenger

This is the most direct credit example for comparing candidates.

- [Champion/challenger script](https://github.com/joaaomaia/RiskBands/blob/main/examples/pd_vintage_champion_challenger/pd_vintage_champion_challenger.py)
- [Champion/challenger notebook](https://github.com/joaaomaia/RiskBands/blob/main/examples/pd_vintage_champion_challenger/pd_vintage_champion_challenger.ipynb)

### PD vintage benchmark

This is the strongest methodology showcase in the project today.

- [Benchmark script](https://github.com/joaaomaia/RiskBands/blob/main/examples/pd_vintage_benchmark/pd_vintage_benchmark.py)
- [Benchmark notebook](https://github.com/joaaomaia/RiskBands/blob/main/examples/pd_vintage_benchmark/pd_vintage_benchmark.ipynb)

Use this material when the main question is:

> why can a candidate with stronger aggregate IV still be the wrong choice for credit when time enters the decision?

### `stable` score demo

This is the minimal example for seeing the change between the legacy score and
the current recommended temporal strategy.

- [Demo script](https://github.com/joaaomaia/RiskBands/blob/main/examples/stable_score/stable_score_demo.py)

## Suggested reading order

### If you want to start with the API

1. Synthetic notebook with Plotly
2. Quickstart
3. API overview
4. Outputs and diagnostics
5. Missing policy
6. PD vintage champion/challenger
7. PD vintage benchmark

### If you want to start with the methodology

1. Why RiskBands
2. Why not only OptimalBinning
3. PD vintage benchmark
4. How to read the charts
