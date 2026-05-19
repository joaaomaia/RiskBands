# Missing policy methodological guide

This guide helps reviewers choose among the RiskBands missing-value policies in
v2.3.0. It is methodological guidance, not a regulatory certification. Every
choice should still be reviewed against the project data, controls, sampling
design, and model-governance process.

## Policy selection

Use `missing_policy="standard"` when the current RiskBands treatment is the
desired baseline, when compatibility is more important than explicit missing
segmentation, or when the missing volume is known to be immaterial. `standard`
is the default and should remain the first comparison point.

Use `missing_policy="separate_bin"` when missingness is informative enough to
monitor as its own segment. This is often the most transparent choice for model
risk review because the missing group keeps its own volume, event rate, WoE,
and IV contribution. It is also the safest contrast before considering merge.

Use `missing_policy="forbid"` when missing values indicate an upstream data
quality failure or when the modeling contract requires fully observed inputs.
This policy is useful in production checks because it fails explicitly during
`fit` or `transform` instead of silently routing missing values.

Use `missing_policy="merge"` with
`missing_merge_criterion="nearest_event_rate"` when the missing group should be
audited but routed into the regular bin whose fit-time event rate is closest.
This criterion is easy to explain in terms of observed bad-rate distance.

Use `missing_policy="merge"` with `missing_merge_criterion="nearest_woe"` when
the review needs the missing group routed by scorecard-similarity in WoE space.
It can be more aligned with downstream scorecard interpretation, but it depends
on finite and stable WoE estimates.

Do not use merge just because it reduces the number of visible bins. Do not use
merge when the missing group is large and materially different from every
candidate, when the candidate distances are unstable, when the missing pattern
may encode unavailable future information, or when separate monitoring is more
defensible.

## Reading the audit artifacts

Start with `missing_profile_`. For each variable with missing values it records
fit-time missing count, share, events, event rate, WoE when available, backend,
policy, and merge status. Use this table to decide whether the missing group is
rare, frequent, event-heavy, event-light, or operationally meaningful.

Read `missing_decision_log_` next. For merge, it records the requested policy,
criterion, fallback, selected bin, selected-bin event rate/WoE, distance metric,
distance value, candidate count, tie-break fields, and whether fallback was
used. This is the primary trace of the decision.

Read `missing_merge_candidates_` when merge is used. It lists every regular
candidate considered, the candidate rank, event rate, WoE, distance values,
and selected flag. A defensible merge should have a selected candidate whose
distance is explainable, not merely technically available.

Compare every merge run against `separate_bin`. The separate-bin result shows
what is lost when the missing group is no longer visible as a final bin. Review
changes in IV, bin count, event rate, WoE, and any stability metric by period.

## Risk controls

Leakage: missingness can encode process timing, data availability, channel
behavior, or downstream decisions. If missingness is caused by information that
would not exist at decision time, neither separate-bin nor merge makes the
feature safe. Fix the data contract first.

Small samples: event-rate and WoE distances become fragile when either the
missing group or the candidate bins have low counts. Treat tie-breaks and small
distance differences as review signals, not automatic approval.

Very rare missing: a rare missing group may look close to a candidate by chance.
Prefer `standard` or `forbid` when missing is unexpected; prefer
`separate_bin` when the rare group still needs monitoring.

Very frequent missing: a frequent missing group can dominate the merged bin and
change its event rate, WoE, and IV. Review `metrics_before`,
`metrics_after`, `bin_summary`, and `fit_profile_` before accepting the merge.

Fallbacks: `missing_merge_fallback="separate_bin"` keeps transform-time missing
as `Missing` when no fit-time merge decision exists.
`missing_merge_fallback="raise"` fails explicitly in that situation. Pick the fallback based on the
production contract, not convenience.

## PySpark boundary

In v2.3.0, full PySpark merge is intentionally not implemented. PySpark fit or
transform with `missing_policy="merge"` raises an explicit
`NotImplementedError`. PySpark remains available for supported policies such as
`standard`, `separate_bin`, and `forbid`, including validation paths covered by
the test suite.

## Not implemented in this release

The following features are future work and should not be documented as
available behavior:

- `temporal_stable`;
- `monotonic_neighbor`;
- full PySpark missing merge.

Use the current audit artifacts to compare policies today. Do not infer that
future criteria already exist, and do not create local policy names outside the
public v2.3.0 contract.
