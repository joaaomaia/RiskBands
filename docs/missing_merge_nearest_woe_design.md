# Missing Merge Nearest WOE Design

This internal note documents the Sprint E2 implementation of
`missing_policy="merge"` with `missing_merge_criterion="nearest_woe"`. It is
not a release note and does not imply package publication.

## API

The supported merge criteria are:

```python
RiskBands(
    missing_policy="merge",
    missing_merge_criterion="nearest_event_rate",
)

RiskBands(
    missing_policy="merge",
    missing_merge_criterion="nearest_woe",
)
```

`missing_merge_fallback` remains `separate_bin` by default and also accepts
`raise`. The default `missing_policy` remains `standard`. `legacy` remains a
compatibility alias for `standard` and cannot be combined with merge criteria.

## Fit Semantics

During pandas fit, `nearest_woe` follows the same auditable flow introduced for
`nearest_event_rate`:

1. Keep missing values visible as a pre-merge `Missing` group.
2. Build the pre-merge fit profile with the existing WOE calculation.
3. Read the missing group's WOE from that profile.
4. Read each regular candidate bin's WOE from that profile.
5. Exclude candidates with non-finite WOE.
6. Select the candidate with the smallest `abs(missing_woe - candidate_woe)`.
7. Break ties by larger candidate `n`, lower `bin_order`, then label.
8. Persist the learned destination and full candidate audit payload.

No transform or application data participates in the decision.

## Event Rate Versus WOE

`nearest_event_rate` selects by absolute event-rate distance. `nearest_woe`
selects by absolute WOE distance. These can choose different bins because WOE
uses smoothed event and non-event distributions from the fit profile rather
than raw event-rate differences.

The WOE values are not recalculated in a separate implementation. They come
from the same profile used elsewhere by RiskBands, including the existing 0.5
smoothing for zero-event or all-event groups.

## Audit Trail

`missing_decision_log_` records:

- `merge_criterion="nearest_woe"`
- `missing_woe`
- `selected_bin_woe`
- `distance_woe`
- `distance_metric="abs_woe_diff"`
- `candidate_bins` with bin label, `n`, event rate, WOE, distance, and selected
  flag
- tie-break and fallback metadata

`missing_merge_candidates_` stores the tabular candidate payload, and
`missing_profile_` keeps the original missing group visible even after the final
`bin_summary` removes the standalone `Missing` row for merged variables.

## Transform And Return WOE

Transform uses only the fit-time `missing_merge_map_`. It does not inspect
target values, application event rates, application WOE, or OOT distributions.

With `return_woe=True`, missing values are first routed to the learned
destination label and then mapped to the final fitted WOE for that destination
bin. If no decision was learned because no missing values appeared during fit,
`separate_bin` keeps the transform label as `Missing`; requesting WOE for that
fallback raises because there is no fitted WOE for a new transform-only missing
bin. With fallback `raise`, transform fails when new missing values appear.

## Bundle And Reporting

Bundle export persists:

- `missing_policy`
- `effective_missing_policy`
- `missing_merge_criterion`
- `missing_merge_fallback`
- `missing_profile`
- `missing_decision_log`
- `missing_merge_candidates`
- `missing_merge_map`

Reports expose the selected criterion, destination bin, generic merge distance,
distance metric, event-rate distance, and WOE distance.

## PySpark Boundary

v2.4.0 supports Spark missing merge through the narrow sampled-to-pandas fit and
native Spark transform path documented in the PySpark design notes. This applies
to both `nearest_event_rate` and `nearest_woe`, with sampling caveats captured in
metadata, bundle, validation reports, and `audit_report.html`.

Spark-native full-data merge learning and Spark `return_woe=True` remain outside
the current public contract.

## Out Of Scope

E2 does not implement:

- `temporal_stable`
- `monotonic_neighbor`
- custom criteria
- advanced thresholds
- Spark-native full-data merge learning
- Spark `return_woe=True`
- publication, tags, or automatic pushes
