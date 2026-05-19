---
title: "Outputs and diagnostics"
description: "How to interpret the main Binner outputs after fit, with a focus on audit, score, and temporal reading."
---

## What appears after `fit`

After fitting a `Binner`, the public API exposes friendly artifacts:

- `binning_table()`
- `feature_binning_table()` and `get_binning_table()`
- `summary()`
- `score_details()`
- `score_table()`
- `report()`
- `audit_table()`
- `diagnostics()`
- `plot_stability()`
- `plot_bad_rate_over_time()`
- `plot_bad_rate_heatmap()`
- `plot_bin_share_over_time()`
- `plot_score_components()`
- `export_binnings_json()`
- `export_bundle()`

Useful post-fit attributes are also available, such as:

- `binning_table_`
- `summary_`
- `score_details_`
- `score_table_`
- `audit_table_`
- `report_`
- `metadata_`
- `score_`
- `comparison_score_`

## Main tables

`binning_table()` shows final cuts or bins. `score_table()` is the short table
for explaining the objective, weights, normalized components, and raw
components. `audit_table()` combines cuts, IV, temporal score, penalties,
coverage, rare bins, reversals, and summarized rationale.

## Temporal diagnostics

Use `diagnostics(kind="bin")` to open detail by bin and period. Use
`diagnostics(kind="variable")` for the aggregated temporal summary by variable.

This is the best entry point to investigate:

- coverage
- event-rate volatility
- WoE volatility
- bin share
- ranking reversals
- monotonicity breaks

## Metadata

`metadata_` includes the `riskbands` version, strategy, `score_strategy`,
`normalization_strategy`, `woe_shrinkage_strength`, weights, `target_name`,
`time_col`, and fitted features.

## Auditable export

`export_binnings_json(path)` generates a single JSON with metadata, score
weights, bins by feature, summary, score details, and feature-level audit.

`export_bundle(path)` generates readable JSON, CSVs, feature-level tables, and
optional Parquet when an engine is available.

Bundles also persist the missing-values trail when available:
`missing_policy`, `effective_missing_policy`, `missing_profile`,
`missing_decision_log`, `missing_merge_criterion`, `missing_merge_fallback`,
`missing_merge_candidates`, and `missing_merge_map`.

These fields record the missing-values treatment decision. They do not
represent opaque imputation.

Use `missing_profile_` to review missing volume, share, and event rate by
variable. Use `missing_decision_log_` to see whether the action was to preserve
`standard`, create a `Missing` bin with `separate_bin`, block with `forbid`, or
route missing values with `merge`. For merge, use `missing_merge_candidates_`
to review candidates and distances and `missing_merge_map_` to see the learned
destination.

Dedicated guide: [Missing policy](../missing-policy/).

## Fast score reading

- `standard`: higher raw score is better
- `stable`: lower raw score is better

For a consolidated scale across strategies, also look at
`objective_preference_score`.

## Example

```python
binner.fit(df, y="target", column="score", time_col="month")

table = binner.binning_table()
score_table = binner.score_table()
audit_table = binner.audit_table()

binner.export_binnings_json("artifacts/riskbands_binnings.json")
binner.export_bundle("artifacts/run_2026_04_14")
```
