# Missing Merge Nearest Event Rate Design

This note documents the internal E1 implementation of auditable missing-value
merge behavior. It is not a public release note and does not imply a published
version.

## Implemented API

The E1 API adds a narrow merge mode:

```python
RiskBands(
    missing_policy="merge",
    missing_merge_criterion="nearest_event_rate",
    missing_merge_fallback="separate_bin",
)
```

Supported values in this sprint:

- `missing_policy`: `standard`, `separate_bin`, `forbid`, `merge`.
- `missing_merge_criterion`: `nearest_event_rate` only.
- `missing_merge_fallback`: `separate_bin` or `raise`.

`legacy` remains a compatibility alias for `standard`. The default
`missing_policy` remains `standard`.

## Fit Behavior

During pandas fit, merge mode treats missing values as an observable training
group before final routing:

1. Detect missing values for each fitted variable.
2. Build an internal profile where missing is visible as `Missing`.
3. Compute the missing group's event rate.
4. Compute event rates for regular candidate bins.
5. Select the candidate with the smallest absolute event-rate distance.
6. Break ties by larger candidate `n`, then lower `bin_order`.
7. Persist the selected mapping and candidate audit data.
8. Remove the standalone `Missing` row from final `bin_summary` for variables
   whose missing group was merged.

The final transform output routes missing values to the learned destination bin,
but the original missing group remains visible in audit fields.

## Transform Behavior

Transform never learns a merge decision. It only uses fit-time decisions stored
in `missing_merge_map_`.

If missing values were not observed during fit and appear during transform:

- `missing_merge_fallback="separate_bin"` returns `Missing`.
- `missing_merge_fallback="raise"` raises a clear error.

The transform fallback path records `missing_transform_fallback_log_`.

## Audit Trail

The implementation preserves missing visibility through:

- `missing_profile_`
- `missing_decision_log_`
- `missing_merge_candidates_`
- `missing_merge_map_`
- `missing_transform_fallback_log_`

Important decision log fields include:

- `missing_merge_criterion`
- `missing_merge_fallback`
- `event_rate_missing_fit`
- `selected_bin_label`
- `selected_bin_event_rate`
- `distance`
- `tie_break_applied`
- `candidate_bins`
- `metrics_before`
- `metrics_after`
- `training_only`

Bundle export and JSON/Excel report paths persist the merge audit fields.

## PySpark Boundary

E1 does not implement PySpark merge routing. PySpark fit or transform with
`missing_policy="merge"` raises:

```text
missing_policy="merge" with PySpark is not implemented in this release. Use pandas fit/transform or missing_policy="separate_bin"/"forbid".
```

Existing Spark behavior for `standard`, `separate_bin`, and `forbid` remains in
scope and is covered by Spark regression tests.

## Limitations

- No `nearest_woe` criterion.
- No `temporal_stable` criterion.
- No `monotonic_neighbor` criterion.
- No custom criterion.
- No threshold tuning beyond exact nearest event-rate distance.
- No full PySpark implementation.
- No use of transform/OOT target data to choose a merge destination.

## Future Work

Sprint E2 can add `nearest_woe` if the WOE definition and smoothing rules are
made explicit for low-count or zero-event bins.

Later sprints can consider:

- `temporal_stable`, using period-level missing and candidate stability.
- `monotonic_neighbor`, using ordered-bin constraints.
- Native Spark transform routing when learned pandas merge maps can be applied
  without full DataFrame collection.
- Additional governance controls such as minimum missing count or maximum event
  rate distance.

## Usage Criteria

Use `missing_policy="merge"` only when the missing group is meaningful, should
not be hidden, and routing it to the closest observed risk band is acceptable for
model governance. Prefer `separate_bin` when missingness should remain a visible
standalone segment in transformed data. Prefer `forbid` when missing values must
be resolved upstream.
