# PySpark Missing Merge Transform Design

## G1 scope

Sprint G1 supports the narrow path:

```text
pandas fit -> Spark transform
```

The missing merge decision is still learned only during pandas fit. Spark transform applies the learned decision with native Spark expressions.

## Allowed

- `RiskBands(..., missing_policy="merge").fit(pandas_df, y=...)`
- `binner.transform(spark_df, return_woe=False)` after the pandas fit
- `missing_merge_criterion="nearest_event_rate"`
- `missing_merge_criterion="nearest_woe"`
- `missing_merge_fallback="separate_bin"`
- `missing_merge_fallback="raise"`
- `transform(validate=True)` when the Spark input includes the fitted target column
- `export_bundle(...)` / `load_bundle(...)` preserving merge metadata while the fitted in-memory model continues to transform Spark inputs

## Still blocked

- Spark fit with `missing_policy="merge"`
- Spark `return_woe=True`
- PySpark learning of merge decisions
- Spark sampled-to-pandas fit with merge enabled

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

## Validation

`transform(validate=True)` reuses the Spark aggregate profile path. The application profile is built from final Spark bin labels, so learned missing merges appear in the destination bin and fallback `separate_bin` appears as `"Missing"`.

## Bundle

The audit bundle persists:

- `missing_policy`
- `missing_merge_criterion`
- `missing_merge_fallback`
- `missing_merge_map`
- missing profile and decision logs

`load_bundle(...)` loads these audit fields for review. It does not reconstruct a fitted estimator; Spark transformation remains the responsibility of the fitted in-memory `RiskBands` object.

## Next steps

- G2: design Spark sampled-to-pandas fit support for merge, if still desired.
- G3: refine Spark validation/reporting metadata around missing merge transform fallback logs.
- G4: update public docs and release notes after functional gates are accepted.
