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

- [Quickstart script](https://github.com/joaaomaia/RiskBands/blob/main/examples/temporal_stability/temporal_stability_example.py)
- [Quickstart notebook](https://github.com/joaaomaia/RiskBands/blob/main/examples/temporal_stability/temporal_stability_example.ipynb)

This flow shows `score_table()`, `audit_table()`, JSON/bundle export, and public
plots for temporal reading.

### Missing policy with pandas and PySpark

Use these scripts when the main question is how to handle missing values in an
auditable way without opaque imputation.

- [pandas missing policy demo](https://github.com/joaaomaia/RiskBands/blob/main/examples/missing_policy/missing_policy_pandas_demo.py)
- [PySpark missing policy demo](https://github.com/joaaomaia/RiskBands/blob/main/examples/missing_policy/missing_policy_pyspark_demo.py)

They show:

- `missing_policy="standard"`
- `missing_policy="separate_bin"`
- `missing_policy="forbid"`
- `missing_policy="merge"` with `nearest_event_rate`
- `missing_policy="merge"` with `nearest_woe`
- `missing_profile_`
- `missing_decision_log_`
- `missing_merge_candidates_`
- bundle fields for missing policy and missing merge
- optional guard for PySpark

### PD vintage champion/challenger

- [Champion/challenger script](https://github.com/joaaomaia/RiskBands/blob/main/examples/pd_vintage_champion_challenger/pd_vintage_champion_challenger.py)
- [Champion/challenger notebook](https://github.com/joaaomaia/RiskBands/blob/main/examples/pd_vintage_champion_challenger/pd_vintage_champion_challenger.ipynb)

### PD vintage benchmark

- [Benchmark script](https://github.com/joaaomaia/RiskBands/blob/main/examples/pd_vintage_benchmark/pd_vintage_benchmark.py)
- [Benchmark notebook](https://github.com/joaaomaia/RiskBands/blob/main/examples/pd_vintage_benchmark/pd_vintage_benchmark.ipynb)

Use this material when the main question is why a candidate with stronger
aggregate IV can still be the wrong choice for credit when time enters the
decision.

### `stable` score demo

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
