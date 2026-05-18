---
title: "Outputs and diagnostics"
description: "How to interpret the main Binner outputs after fit, with a focus on audit, score, and temporal reading."
---

## What appears after `fit`

After fitting a `Binner`, the public API exposes friendlier artifacts for
inspection:

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

## `binning_table()`

Use it when you want to see final cuts or bins directly.

Questions it helps answer:

- how many bins were kept?
- which intervals or groups were formed?
- what is the bin order?

## `score_table()`

This is the shortest notebook table when the central question is:

- why did this score come out this way?
- which weights entered?
- which components mattered most?
- which normalization is active?

It exposes:

- `objective_score`
- `objective_preference_score`
- `weight_profile`
- `normalized_component_profile`
- `raw_component_profile`
- detailed `objective_weight_*`, `objective_norm_*`, and `objective_raw_*` columns

## `audit_table()`

This is the most useful table for auditable review and model risk.

It combines in a single view:

- cuts
- IV and temporal score
- score and penalties
- coverage, rare bins, and reversals
- summarized rationale

## `diagnostics()`

Use `diagnostics(kind="bin")` when you want to open detail by bin and period.

Use `diagnostics(kind="variable")` when you want the aggregated temporal
summary by variable.

It is the best entry point to investigate:

- coverage
- event-rate volatility
- WoE volatility
- bin share
- ranking reversals
- monotonicity breaks

## `metadata_`

Post-fit metadata is now more auditable.

It includes:

- `riskbands` version
- `strategy`
- `score_strategy`
- `normalization_strategy`
- `woe_shrinkage_strength`
- provided weights and effective weights
- `target_name`
- `time_col`
- fitted features

## Auditable export

### `export_binnings_json(path)`

Generates a single JSON with:

- general fit metadata
- score weights
- bins by feature
- summary, score details, and audit by feature

### `export_bundle(path)`

Generates an audit package with:

- readable JSON
- CSVs ready for notebooks or governance
- feature-level tables
- optional Parquet when an engine is available

## Fast score reading

A simple rule:

- `standard`: higher raw score is better
- `stable`: lower raw score is better

If you want a consolidated scale for comparison across strategies, also look
at `objective_preference_score`.

Bundles also persist the missing-values trail when available:
`missing_policy`, `effective_missing_policy`, `missing_profile`, and
`missing_decision_log`.

These fields record the missing-values treatment decision. They do not
represent opaque imputation or merge policies.

Use `missing_profile_` to review missing volume, share, and event rate by
variable. Use `missing_decision_log_` to see whether the action was to preserve
`standard` behavior, create a `Missing` bin with `separate_bin`, or block the
flow with `forbid`.

Dedicated guide: [Missing policy](../missing-policy/).

## Example

```python
binner.fit(df, y="target", column="score", time_col="month")

table = binner.binning_table()
score_table = binner.score_table()
audit_table = binner.audit_table()

binner.export_binnings_json("artifacts/riskbands_binnings.json")
binner.export_bundle("artifacts/run_2026_04_14")
```
