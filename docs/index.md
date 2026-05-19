# RiskBands Docs

Entry point for the project documentation.

## Recommended Flow

1. Fit `RiskBands(...).fit(X, y, time_col=...)` or the compatible `Binner(...)` alias.
2. Transform the data with `transform(...)`.
3. Generate the temporal pivot with `stability_over_time(...)`.
4. Inspect the detailed diagnostics with `temporal_bin_diagnostics(...)`.
5. Summarize stability with `temporal_variable_summary(...)`.
6. Consolidate the rationale with `variable_audit_report(...)`.
7. Compare candidates with `BinComparator` when doing champion/challenger.

## Quick Navigation

- [README.md](../README.md)
  Project overview, installation, quickstart, and positioning.
- [docs/api_reference.md](api_reference.md)
  Main API contract and public package surface.
- [docs/v2.2.0_user_guide.md](v2.2.0_user_guide.md)
  v2.2.0 import, missing policies, pandas/PySpark, validation, and bundle guide.
- [docs/missing_policy_user_guide.md](missing_policy_user_guide.md)
  Dedicated guide for `standard`, `separate_bin`, `forbid`, `merge`, pandas/PySpark examples, audit fields, and bundle reporting.
- [docs/missing_policy_methodological_guide.md](missing_policy_methodological_guide.md)
  Methodological guidance for choosing missing policies and reviewing merge decisions.
- [docs/releases/2.3.0.md](releases/2.3.0.md)
  v2.3.0 release-prep notes for auditable missing merge policies.
- [docs/missing_merge_nearest_event_rate_design.md](missing_merge_nearest_event_rate_design.md)
  Internal design note for `missing_merge_criterion="nearest_event_rate"`.
- [docs/missing_merge_nearest_woe_design.md](missing_merge_nearest_woe_design.md)
  Internal design note for `missing_merge_criterion="nearest_woe"`.
- [docs/migration.md](migration.md)
  Breaking migration guide for users coming from `NASABinning`.
- [examples/README.md](../examples/README.md)
  Map of the main examples.
- [examples/pd_vintage_benchmark/pd_vintage_benchmark.py](../examples/pd_vintage_benchmark/pd_vintage_benchmark.py)
  Premium benchmark for credit risk, comparing pure `OptimalBinning` versus RiskBands under temporal stress.
- [examples/pd_vintage_benchmark/pd_vintage_benchmark.ipynb](../examples/pd_vintage_benchmark/pd_vintage_benchmark.ipynb)
  Visual notebook version with benchmark board, vintage heatmaps and penalty breakdown.
- [examples/temporal_stability/temporal_stability_example.py](../examples/temporal_stability/temporal_stability_example.py)
  Minimal temporal quickstart.
- [examples/missing_policy/missing_policy_pandas_demo.py](../examples/missing_policy/missing_policy_pandas_demo.py)
  Small pandas demo for missing-policy behavior, merge with nearest event rate and nearest WoE, audit fields, and bundle roundtrip.
- [examples/missing_policy/missing_policy_pyspark_demo.py](../examples/missing_policy/missing_policy_pyspark_demo.py)
  Small optional PySpark demo for `separate_bin`, `forbid`, and `transform(validate=True)`.
- [examples/missing_policy/missing_policy_comparison_demo.py](../examples/missing_policy/missing_policy_comparison_demo.py)
  Comparative diagnostic for `standard`, `separate_bin`, `forbid`, and both merge criteria.
- [examples/missing_policy/credit_risk_missing_merge_demo.py](../examples/missing_policy/credit_risk_missing_merge_demo.py)
  Synthetic credit-risk example with informative missingness and auditable merge decisions.
- [examples/pd_vintage_champion_challenger/pd_vintage_champion_challenger.py](../examples/pd_vintage_champion_challenger/pd_vintage_champion_challenger.py)
  Credit-risk / PD anchor example with vintages.

## What to Look For in Credit Work

The most relevant components for PD and interpretable scorecard workflows are:

- `temporal_separability_score(...)`
- `temporal_bin_diagnostics(...)`
- `temporal_variable_summary(...)`
- `variable_audit_report(...)`
- `BinComparator` with `candidate_profile_summary()` and `winner_summary()`
- `riskbands.benchmark_plots` when you need reusable Plotly visuals for benchmark demos

## Local Validation

```bash
pytest -q --basetemp .pytest_tmp
```

Light CI workflow:

- [tests.yml](../.github/workflows/tests.yml)
