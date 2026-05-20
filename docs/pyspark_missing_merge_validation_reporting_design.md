# PySpark Missing Merge Validation and Reporting Design

This internal note documents the G3 validation/reporting layer for the Spark missing-merge flow:

```text
fit Spark -> sampled-to-pandas -> missing merge learned on sample -> transform Spark
```

G3 does not add Spark-native full fit, Spark `return_woe=True`, or a new missing merge criterion. It makes the existing sampled fit path more auditable.

## What G3 Improves

G3 adds explicit diagnostics for the gap between the sampled pandas-core fit and the full Spark source data used to draw that sample. The main additions are:

- aggregated Spark `source_profile_` when `fit(validate=True)` is used;
- sample-vs-source bin diagnostics in `fit_validation_report_["sample_representativeness"]`;
- per-variable `missing_sampling_diagnostics`;
- richer `fit_validation_report_` metadata for Spark sampled fit;
- richer `transform_validation_report_` comparison payloads;
- bundle and audit report caveats for sampled-to-pandas missing merge;
- static guards that keep profile collection limited to guarded aggregate rows.

## Source Profile

For Spark fit with validation enabled, RiskBands builds `source_profile_` with Spark aggregations by variable and final bin label. The profile is collected only after aggregation and only through the guarded `_collect_pyspark_profile_aggregate` helper.

If the aggregate profile exceeds `max_profile_rows_to_collect`, source profiling is skipped and `fit_validation_report_["summary"]["source_profile_status"]` records `skipped_profile_too_large`.

When missing merge is learned, `source_profile_` reflects final bins after the learned merge decision. It is not a raw missing-value profile and should not be interpreted as proof that source missing values were represented in the sample.

## Sample vs Source

`fit_validation_report_["sample_representativeness"]` compares `fit_profile_` from the sampled fit against `source_profile_` from Spark aggregation. It records:

- `event_rate_abs_diff`;
- `share_abs_diff`;
- bins present in source but absent in the sampled fit;
- bins present in the sampled fit but absent in source;
- bounded per-bin diagnostics.

These diagnostics can produce warnings such as `sample_event_rate_shift`, `sample_share_shift`, and `profile_too_large`.

## Missing Sampling Diagnostics

`missing_sampling_diagnostics` is a per-variable list with:

- `missing_share_sample_fit`;
- `missing_share_source_spark`;
- `missing_share_abs_diff`;
- `missing_count_sample_fit`;
- `missing_count_source_spark`;
- `missing_merge_destination_learned`;
- `merge_decision_learned_on_sample`;
- `fallback_risk`;
- `alert_flags`.

The most important warning is `source_missing_not_seen_in_sample`: the full Spark source has missing values, but the sampled fit did not. If no merge decision was learned while source missing exists, the diagnostic also records `merge_decision_not_learned_but_source_has_missing`.

These warnings are not approvals. They make sampling risk visible so reviewers can decide whether to increase `sample_size`, adjust sampling upstream, or rely on fallback behavior.

## Fit Validation Report

For Spark sampled fit, `fit_validation_report_` now includes:

- `backend="pyspark"`;
- `fit_mode="sampled_to_pandas"`;
- source and fit row counts;
- sampling request/effective fraction fields;
- `sample_representativeness`;
- `missing_sampling_diagnostics`;
- `merge_decision_summary`;
- consolidated alerts.

`validation_report_` still aliases `fit_validation_report_` immediately after `fit(validate=True)`.

## Transform Validation Report

Spark `transform(validate=True)` still builds `application_profile_` through Spark aggregation. It compares the application profile against `reference_profile_`, which prefers `source_profile_` when available and falls back to `fit_profile_`.

The transform report records:

- target availability and skipped status when target is absent;
- application-vs-reference event-rate alerts;
- application-vs-reference share-shift alerts;
- bins missing on either side of the comparison;
- bounded per-bin comparison records.

Transform validation does not learn event rates, WoE, or missing merge destinations from application data.

## Bundle and Audit Report

Bundles persist:

- `source_profile`;
- `reference_profile`;
- `application_profile`;
- fit and transform validation reports;
- `missing_sampling_diagnostics`;
- sampling metadata and source missing counts in metadata.

The narrative audit report includes caveats for sampled-to-pandas fit, distinguishes whether a merge decision was learned on sample, and calls out source missing values not seen in the sample.

## Remaining Limits

G3 preserves these limits:

- no Spark-native full fit;
- no Spark `return_woe=True`;
- no new merge criterion;
- no full source collect for validation/reporting;
- no claim that a warning means the sample is representative.

## Release Prep Notes

Before release prep, run the Spark gates, audit report regressions, static guards, and bundle roundtrip tests. Public docs should describe these diagnostics as audit/validation aids, not as representativeness guarantees.
