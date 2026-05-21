# PySpark Missing Merge Transform Design

## G1 scope

Sprint G1 supports the narrow path:

```text
pandas fit -> Spark transform
```

The missing merge decision is still learned only during pandas fit. Spark transform applies the learned decision with native Spark expressions.

## G1B hardening status

Sprint G1B does not add API surface. It hardens the same G1 path with adversarial tests and regression gates around pandas/Spark equivalence, multi-feature transforms, missing detection, validation, bundle metadata, and static source guards.

## G2 sampled-fit status

Sprint G2 adds a narrow fit boundary:

```text
Spark fit -> controlled sample -> pandas core missing merge -> Spark transform
```

The missing merge decision is learned on sampled pandas rows, not on the full Spark DataFrame. See `docs/pyspark_missing_merge_sampled_fit_design.md` for the fit-side contract, metadata fields, and caveats.

## Allowed

- `RiskBands(..., missing_policy="merge").fit(pandas_df, y=...)`
- `RiskBands(..., missing_policy="merge").fit(spark_df, y=...)` through sampled-to-pandas only
- `binner.transform(spark_df, return_woe=False)` after the pandas fit
- `binner.transform(spark_df, return_woe=False)` after the Spark sampled fit
- `missing_merge_criterion="nearest_event_rate"`
- `missing_merge_criterion="nearest_woe"`
- `missing_merge_fallback="separate_bin"`
- `missing_merge_fallback="raise"`
- `transform(validate=True)` when the Spark input includes the fitted target column
- `transform(validate=True)` without the target column, returning a skipped transform validation report
- `export_bundle(...)` / `load_bundle(...)` preserving merge metadata while the fitted in-memory model continues to transform Spark inputs

## Still blocked

- Spark `return_woe=True`
- Spark-native learning of merge decisions
- Any implication that sampled merge decisions were learned on the full Spark DataFrame

## Spark transform semantics

For every selected feature, Spark first uses the existing native expression to map regular values to fitted bins.

For numeric supervised features:

- `NULL` is missing.
- `NaN` is missing for Spark `FloatType` and `DoubleType`.
- If `missing_merge_map_[feature]` exists, missing values return the learned destination bin label.
- If no decision exists and fallback is `separate_bin`, missing values return `"Missing"`.
- If no decision exists and fallback is `raise`, Spark aggregates missing counts for the affected feature and raises before applying the transform.

For categorical features:

- `NULL` is missing.
- Non-null unknown categories keep the fitted unknown/default-bin behavior.
- The pandas internal `_MISSING_` token remains an implementation detail and is not used as a Spark input sentinel.

For multi-feature transforms:

- `columns=[...]` selects only fitted features requested by the caller.
- Extra columns in the Spark input are not included in the transform output.
- `missing_merge_map_` is applied independently per selected feature.
- If one selected feature has no learned missing decision, fallback handling is scoped to that feature.

## Validation

`transform(validate=True)` reuses the Spark aggregate profile path. The application profile is built from final Spark bin labels, so learned missing merges appear in the destination bin and fallback `separate_bin` appears as `"Missing"`.

If the fitted target column is absent from the Spark input, validation is skipped with `reason == "target_not_available"` and no application profile is created. The reference profile from fit is not modified by transform validation.

## Bundle

The audit bundle persists:

- `missing_policy`
- `missing_merge_criterion`
- `missing_merge_fallback`
- `missing_merge_map`
- sampled-fit caveat metadata when Spark fit used sampled-to-pandas
- missing profile and decision logs
- missing merge candidate tables
- Spark transform fallback logs when a fallback error is observed before export

`load_bundle(...)` loads these audit fields for review. It does not reconstruct a fitted estimator; Spark transformation remains the responsibility of the fitted in-memory `RiskBands` object.

## Static guard

G1B adds tests that inspect the direct Spark transform methods and block accidental introduction of:

- Python UDFs
- pandas UDFs
- `.collect(` in direct transform expressions
- `.toPandas(` in direct transform expressions

Collection remains allowed only in named aggregate/profile helpers, such as missing-count aggregation for fallback `raise` and bounded validation profile collection.

## Release boundary

The v2.4.0 release-prep documents this as supported Spark missing merge
behavior with the limits above. Spark-native full fit, Spark `return_woe=True`,
and callable estimator reconstruction from `load_bundle(...)` remain outside
the current public contract.
