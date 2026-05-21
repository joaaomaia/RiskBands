---
title: "Release Notes"
description: "High-level release milestones for the public package and the official documentation."
---

## v2.4.0

Type: compatible minor release preparation.

Main points:

- Spark transform supports `missing_policy="merge"` when a merge decision was learned, using native Spark expressions and `return_woe=False`
- Spark fit with missing merge uses a controlled sampled-to-pandas path and records that the merge decision was learned on the sample
- Spark validation/reporting adds `source_profile_`, sample-vs-source diagnostics, and `missing_sampling_diagnostics`
- metadata, bundle outputs, and `audit_report.html` carry sampling caveats for Spark sampled fit
- `audit_report.html` is a narrative standalone HTML report with embedded CSS, print-friendly layout, missing policy explanations, bundle inventory, validation alerts, and limitations
- `export_bundle(...)` includes `audit_report.html` by default
- docs-site includes a Reveal.js presentation gallery and RiskBands overview deck
- pt-BR/en docs and examples cover missing policy, audit bundle/reporting, and Spark missing merge behavior

Notes:

- `missing_policy="standard"` remains the default
- Spark-native full fit is not part of this release target
- Spark `return_woe=True` is still not supported
- no `temporal_stable`, `monotonic_neighbor`, custom merge criteria, opaque imputation, or PySpark 4.x support is added
- the audit report supports review, but it does not replace independent formal validation or guarantee regulatory compliance
- `joblib/PYSEC-2024-277` is handled as a documented `pip-audit` exception with no fixed version available; only that advisory is ignored, and the decision is recorded in `docs/security/pip_audit_exceptions.md`

## v2.3.0

Type: compatible minor release.

Main points:

- `missing_policy="merge"` adds auditable missing-value merge for pandas workflows
- `missing_merge_criterion="nearest_event_rate"` selects the closest regular bin by fit-time event-rate distance
- `missing_merge_criterion="nearest_woe"` selects the closest regular bin by fit-time WoE distance
- `missing_merge_fallback` supports `separate_bin` and `raise`
- `missing_profile_`, `missing_decision_log_`, `missing_merge_candidates_`, and `missing_merge_map_` preserve the audit trail
- `return_woe=True` routes merged missing values to the learned destination bin before mapping WoE
- bundle and reporting exports persist merge criterion, fallback, candidates, decision log, and merge map
- `standard`, `separate_bin`, `forbid`, `legacy` alias compatibility, and `RiskBands is Binner` are preserved
- pt-BR/en docs and examples describe both merge criteria

Notes:

- `missing_policy="standard"` remains the default
- PySpark merge is not implemented; PySpark raises an explicit boundary for `missing_policy="merge"`
- no `temporal_stable`, `monotonic_neighbor`, custom merge criteria, opaque imputation, or PySpark 4.x support is added

## Documentation update after v2.2.0

Type: docs-only preparation.

Status: documentation update after v2.2.0; no package version bump.

Main points:

- adds a focused missing-policy guide for `standard`, `separate_bin`, and `forbid`
- adds small pandas and PySpark missing-policy demos
- improves docs-site navigation for missing values, bundle fields, and audit logs
- keeps PySpark documented as optional through `riskbands[spark]`
- does not change core behavior, package version, publish status, tag, or release artifacts

Historical notes:

- at that documentation point, merge policies remained future work
- no opaque intelligent imputation is added
- i18n is handled as a later docs-site sprint, without changing package release status

## v2.2.0

Compatible minor release focused on auditable missing-value policy and compatibility.

Main points:

- `missing_policy="standard"` is the default and preserves the Sprint A baseline behavior
- `missing_policy="separate_bin"` is opt-in and creates explicit `Missing` bins, including categorical missing values
- `missing_policy="forbid"` raises during `fit` or `transform` when selected features contain missing values
- `standard` is the canonical name for the historical maximize-oriented score strategy
- `legacy` remains accepted as a compatibility alias for `standard`
- pandas and PySpark inputs are supported by the missing-policy contract
- bundles persist `missing_policy`, `effective_missing_policy`, `missing_profile`, and `missing_decision_log`
- old bundles without these fields continue to load as `standard`
- PySpark remains optional through `riskbands[spark]` with `pyspark>=3.5,<4`

Notes:

- merge policies such as `merge_nearest_woe` and `merge_nearest_event_rate` are not part of this target
- no opaque intelligent imputation is added
- a full distributed Spark fitting backend is not part of this target

## v2.1.0

Compatible minor release focused on the preferred `RiskBands` name, optional
PySpark paths, and validation profiles.

Main points:

- `RiskBands` is the preferred public estimator name; `Binner` remains compatible
- `min_n_bins` records a soft quality status without forcing artificial cuts
- `sample_size` controls PySpark fit sampling
- pandas/PySpark inputs are detected automatically in `fit` and `transform`
- pandas outputs remain pandas; PySpark outputs remain PySpark
- `fit(validate=True)` and `transform(validate=True)` create validation profiles with separate fit and transform reports
- v2.1.0 bundles persist schema/version metadata, profiles, separate validation reports, sampling/backend metadata, and data schema when available
- PySpark remains optional through `riskbands[spark]` with `pyspark>=3.5,<4`

Notes:

- PySpark fit uses controlled sampling plus the current pandas engine
- PySpark transform and validation profiles use native Spark expressions and aggregated profiles
- A full distributed Spark fitting backend is not part of this release

## v2.0.3

Patch release focused on release hardening and deterministic operational behavior.

Main points:

- stronger categorical handling for rare categories, missing values, and unknown categories
- safer `export_bundle(...)` outputs with sanitized names and a traceable manifest
- explicit `force_numeric` support
- stronger quality gates with `ruff`, coverage-enabled `pytest`, `pip check`, `bandit`, and `pip-audit`
- supply-chain constraints to avoid the vulnerable `ortools 9.11.4210 -> protobuf 5.26.1` resolver path
- README and release governance updates for pandas, Spark/Databricks usage, overrides, auditable export, assets, and local prompts

## v2.0.2

Release focused on real auditability, friendlier inspection, and a more robust
public experience.

Main points:

- new public export layer with `export_binnings_json(...)`
- new auditable bundle with `export_bundle(...)`
- stronger `metadata_`, including score weights and effective fit context
- new public tables `score_table()` and `audit_table()`
- more discoverable aliases for bin inspection
- new public plot layer for bad rate, heatmap, temporal share, and score components
- fix to temporal alignment in the supervised strategy, improving diagnostics and visualizations
- documentation benchmark assets regenerated with wider charts and fewer empty traces
- docs site reinforced for onboarding, audit, and visual interpretation

## v2.0.1

Patch release to close the public publication with consistency:

- fixes `riskbands.__version__` resolution in the installed package outside the source tree
- adds regression test for distributed metadata version reading
- fully preserves the rename to `stable`, the new documentation, and the release flow for the `v2` series

## v2.0.0

Public consolidation release:

- definitive rename of the public `score_strategy` value from `generalization_v1` to `stable`
- removal of the old name from the public API, examples, smoke tests, labels, and main documentation
- docs site reorganized for onboarding, first steps, and clearer navigation for new users
- dedicated pages for `score_strategy`, `normalization_strategy`, `woe_shrinkage_strength`, Optuna, and output interpretation
- notebooks and examples aligned with the friendly sklearn/pandas-style flow
- explicit release flow preparation for validation, GitHub Pages, and PyPI publication through Trusted Publishing

## v1.2.0

Important evolution of public API ergonomics:

- `Binner` more aligned with sklearn and pandas conventions
- friendly support for `fit(df, y="target", column="feature")`
- `transform(...)` and `fit_transform(...)` with more predictable behavior for `DataFrame` and `Series`
- public aliases such as `max_n_bins` and `monotonic_trend`
- new inspection methods: `binning_table()`, `summary()`, `report()`, `score_details()`, `diagnostics()`, and `plot_stability()`
- easier-to-discover post-fit attributes
- new Plotly notebook with synthetic data for library onboarding

## v1.1.0

Important evolution of the scoring layer:

- legacy path preserved explicitly as `legacy`
- new temporal objective introduced and now exposed publicly as `stable`
- configurable weights, `absolute` normalization, and WoE shrinkage
- consistent integration with `Binner`, `BinComparator`, auditable reports, and Optuna
- new minimal example comparing `legacy` versus `stable`

## v1.0.0

Important structural changes already reflected in the repository:

- destructive rename to `riskbands`
- `Binner` established as the main public class
- legacy `nasabinning` namespace removed
- documentation direction oriented toward benchmarks established in repository examples
