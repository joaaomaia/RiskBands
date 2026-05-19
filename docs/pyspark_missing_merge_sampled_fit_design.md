# PySpark Missing Merge Sampled Fit Design

## G2 scope

Sprint G2 allows the controlled path:

```text
Spark DataFrame -> bounded sample -> pandas core fit -> Spark transform
```

This is not a Spark-native missing merge fit. The fitted merge destination for
`missing_policy="merge"` is learned by the existing pandas core on the sampled
fit rows. Transform then applies the learned `missing_merge_map_` with native
Spark expressions.

## Allowed

- `RiskBands(..., missing_policy="merge", missing_merge_criterion="nearest_event_rate").fit(spark_df, y="target")`
- `RiskBands(..., missing_policy="merge", missing_merge_criterion="nearest_woe").fit(spark_df, y="target")`
- `missing_merge_fallback="separate_bin"` when the sample has no learned missing decision
- `missing_merge_fallback="raise"` when transform data contains missing values but no decision was learned
- `fit(..., validate=True)` with Spark aggregate source profiles
- `transform(spark_df, return_woe=False)` after Spark sampled fit
- `export_bundle(...)`, `load_bundle(...)`, and `audit_report.html` for reviewing sampled-fit metadata

## Still blocked

- Spark-native learning of missing merge decisions
- Spark `return_woe=True`
- New merge criteria beyond `nearest_event_rate` and `nearest_woe`
- `temporal_stable` and `monotonic_neighbor`
- Rehydrating a callable fitted estimator from `load_bundle(...)`
- New dependencies, version changes, publication, tags, or automatic push

## Sampling contract

`sample_size` controls how many Spark rows may be collected into pandas for fit.
Integer values are treated as an absolute cap; float values in `(0, 1]` are
treated as a sampling fraction. The sampled Spark frame is converted with
`toPandas()` and passed to the pandas core fit.

If the random sample is empty while the source Spark frame is not empty, one
bounded row is collected as a fallback so fit can fail or proceed deterministically
through the normal pandas validation path.

## Caveat and metadata

For Spark fit with `missing_policy="merge"`, metadata records that the merge
decision was learned from the sample:

- `merge_decision_learned_on_sample`
- `merge_decision_fit_mode`
- `merge_decision_n_rows_source`
- `merge_decision_n_rows_fit`
- `merge_decision_sample_size_requested`
- `merge_decision_sample_size_type`
- `merge_decision_sample_fraction_effective`
- `sampling_caveat`

The same scalar fields are copied into `missing_profile_`,
`missing_decision_log_`, and `missing_merge_candidates_` when those tables are
available. Bundle metadata and `audit_report.html` include the caveat so review
artifacts do not imply that the missing merge decision was learned on the full
Spark source.

## Fallback when the sample misses missing values

The full Spark source can contain missing values even when the sampled pandas fit
does not. In that case pandas core records `action == "no_missing_detected"` and
`missing_merge_map_` has no destination for that feature.

At Spark transform time:

- `missing_merge_fallback="separate_bin"` routes missing values to `"Missing"`.
- `missing_merge_fallback="raise"` performs a Spark aggregate missing-count check
  for features without a learned decision and raises a clear `ValueError` only
  when missing values are present.
- Non-missing transform data does not fail under `raise`.

## Validation

`fit(spark_df, validate=True, missing_policy="merge")` keeps the pandas fit
profile from the sample and builds an optional Spark source profile through
bounded aggregate collection. When the source profile is available,
`reference_profile_` uses it and `fit_validation_report_` records the sampled fit
row count, source row count, and sample/source representativeness status.

## Static safety rules

The direct Spark transform path must not use Python UDFs, pandas UDFs, direct
full-data `.collect()`, or direct full-data `.toPandas()`. Collection remains
allowed only for:

- the controlled sampled-to-pandas fit frame;
- the one-row empty-sample fallback;
- aggregate missing-count/profile helpers with row guards.

## G3 candidates

- Decide whether Spark-native missing merge fit is needed.
- Decide whether bundle loading should reconstruct a callable estimator.
- Consider stratified or representativeness-aware sampling controls without
  changing the G2 merge criteria.
