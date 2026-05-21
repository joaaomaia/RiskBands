# API Reference

## Public Surface

```python
from riskbands import (
    RiskBands,
    Binner,
    BinComparator,
    temporal_separability_score,
    ks_over_time,
    psi_over_time,
)
```

Current version:

- `2.4.0`

## `RiskBands` / `Binner`

`RiskBands` is the preferred primary constructor of the library. `Binner` remains a compatible alias for existing code.

Common parameters:

- `strategy`: `"supervised"` or `"unsupervised"` for numeric variables
- `max_bins`: default upper limit for bins
- `max_n_bins`: sklearn/optbinning-friendly alias for `max_bins`
- `min_n_bins`: optional soft quality rule for the minimum number of final regular bins
- `sample_size`: PySpark fit sampling control; positive integers are absolute rows, floats in `(0, 1]` are fractions
- `min_event_rate_diff`: minimum event-rate gap used during refinement
- `monotonic`: `"ascending"`, `"descending"`, or `None`
- `monotonic_trend`: alias for `monotonic`
- `check_stability`: enables temporal checks in the flow
- `use_optuna`: enables hyperparameter search for `strategy="supervised"`
- `time_col`: period column used by temporal diagnostics
- `missing_policy`: `"standard"` (default), `"separate_bin"`, `"forbid"`, or `"merge"`
- `missing_merge_criterion`: required for `missing_policy="merge"`; `"nearest_event_rate"` or `"nearest_woe"`
- `missing_merge_fallback`: `"separate_bin"` (default) or `"raise"` for transform-time missing values when no fit-time merge decision exists
- `score_strategy`: `"standard"` or `"stable"`; `"legacy"` remains a compatibility alias for `"standard"`
- `score_weights`: optional weights for `stable`
- `normalization_strategy`: currently `absolute` for standalone-safe normalization
- `woe_shrinkage_strength`: shrink intensity applied before temporal scoring
- `objective_kwargs`: advanced score configuration override
- `strategy_kwargs`: strategy-specific parameters
  - when `use_optuna=True`, `strategy_kwargs` can also carry search controls such as `n_trials` and `sampler_seed`

Common methods:

- `fit(X, y=None, target=None, column=None, columns=None, time_col=None, validate=False, ...)`
- `transform(X, column=None, columns=None, return_woe=False, return_type="auto", validate=False)`
- `fit_transform(X, y=None, target=None, ..., return_type="auto")`
- `binning_table(column=None, columns=None)`
- `summary(...)`
- `report(...)`
- `score_details(...)`
- `score_table(...)`
- `audit_table(...)`
- `diagnostics(kind="bin" | "variable", ...)`
- `plot_stability(...)`
- `stability_over_time(X, y, time_col, fill_value=None)`
- `temporal_bin_diagnostics(X, y, time_col, dataset_name=None, ...)`
- `temporal_variable_summary(X=None, y=None, diagnostics=None, time_col=None, ...)`
- `variable_audit_report(X=None, y=None, time_col=None, diagnostics=None, summary=None, ...)`
- `feature_binning_table(column=None, feature=None)`
- `get_binning_table(column=None, feature=None)`
- `export_binnings_json(path)`
- `export_audit_report(path, title=None, dataset_name=None)`
- `export_bundle(path, include_audit_report=True)`
- `plot_event_rate_stability(pivot=None, **kwargs)`
- `plot_bad_rate_over_time(X=None, y=None, time_col=None, column=None, ...)`
- `plot_bad_rate_heatmap(X=None, y=None, time_col=None, column=None, ...)`
- `plot_bin_share_over_time(X=None, y=None, time_col=None, column=None, ...)`
- `plot_score_components(column=None, feature=None, ...)`
- `plot_event_rate_by_bin(column=None, feature=None, ...)`
- `plot_woe(X=None, y=None, time_col=None, column=None, ...)`
- `save_report(path)`
- `describe_schema()`
- `get_bin_mapping(column)`

Notes:

- `fit(df, y="target", column="score")` and `fit(df["score"], y=df["target"])` are both valid.
- DataFrame inputs preserve DataFrame outputs; Series inputs return Series by default when `return_type="auto"`.
- `get_params()` and `set_params(...)` work in sklearn style and also understand aliases such as `max_n_bins`.
- `from riskbands import RiskBands as rb` is the recommended short alias style.
- `from riskbands import Binner` remains available for compatibility.
- `save_report("...xlsx")` requires an XLSX writer engine such as `openpyxl` or `xlsxwriter`.

Missing policy semantics:

- `standard`: preserves the current missing-value behavior and is the default.
- `separate_bin`: creates an explicit, auditable `Missing` bin.
- `forbid`: raises a clear error in `fit` or `transform` when selected features contain missing values.
- `merge`: learns a fit-time destination for the missing group and routes missing values to the selected regular bin during pandas transform or supported Spark transform.

For `merge`, use one supported criterion:

- `nearest_event_rate`: selects the candidate bin with the smallest absolute event-rate distance from the fit-time missing group.
- `nearest_woe`: selects the candidate bin with the smallest absolute WoE distance from the fit-time missing group.

The decision is learned only during `fit(...)`; `transform(...)` does not use application target values, application event rates, application WoE, or out-of-time distributions to retarget missing values.

Spark support for `merge` is deliberately narrow. Spark fit uses a controlled
sampled-to-pandas path and records that the merge decision was learned on the
sample, not on a Spark-native full-data fit. Spark transform applies learned
merge decisions with native Spark expressions and currently supports
`return_woe=False` only. No opaque missing-value imputation is added. The
v2.4.0 merge contract does not include `temporal_stable`, `monotonic_neighbor`,
custom criteria, Spark-native full fit, or Spark `return_woe=True`.

For user guidance and runnable examples, see
[`docs/missing_policy_user_guide.md`](missing_policy_user_guide.md) and:

- `examples/missing_policy/missing_policy_pandas_demo.py`
- `examples/missing_policy/missing_policy_pyspark_demo.py`

The main audit attributes are:

- `missing_policy_`
- `effective_missing_policy_`
- `missing_profile_`
- `missing_decision_log_`
- `missing_merge_criterion_`
- `missing_merge_fallback_`
- `missing_merge_candidates_`
- `missing_merge_map_`

These fields are also persisted by `export_bundle(...)` when available.

Main attributes after `fit`:

- `bin_summary`
- `binning_table_`
- `summary_`
- `report_`
- `score_details_`
- `score_table_`
- `audit_table_`
- `metadata_`
- `score_`
- `comparison_score_`
- `diagnostics_` when temporal context is available
- `feature_names_in_`
- `feature_name_` for single-feature fits
- `target_name_`
- `fit_validation_report_` when `fit(validate=True)` was requested
- `transform_validation_report_` when `transform(validate=True)` was requested
- `validation_report_` as the latest validation report compatibility alias
- `fit_profile_`, `source_profile_`, and `reference_profile_` when available
- `missing_sampling_diagnostics_` when Spark sampled-to-pandas fit creates sampling diagnostics
- `missing_policy_`, `effective_missing_policy_`, `missing_profile_`, and `missing_decision_log_`
- `missing_merge_criterion_`, `missing_merge_fallback_`, `missing_merge_candidates_`, and `missing_merge_map_` when merge is enabled
- `iv_`
- `iv_by_variable_`
- `objective_config_`
- `best_params_` when `use_optuna=True`
- `objective_summary_` on binners trained directly with `optimize_bins(...)`
- `objective_summaries_` on multi-feature `Binner` runs with `use_optuna=True`

## Temporal Diagnostics

`temporal_bin_diagnostics(...)` returns an auditable table by variable x bin x period, including:

- `total_count`
- `event_count`
- `non_event_count`
- `bin_share`
- `event_rate`
- `woe`
- `iv_contribution`
- `coverage_flag`
- rarity, coverage, monotonicity, and ranking-reversal flags

`temporal_variable_summary(...)` aggregates that information by variable and exposes:

- mean and minimum temporal coverage
- rare-bin counts
- `event_rate`, `woe`, and `bin_share` volatility
- monotonic-break counts by period
- ranking-reversal counts
- `temporal_score`
- `alert_flags`

## Auditable Reporting

`variable_audit_report(...)` returns a variable-level consolidated table with:

- `cut_summary`
- `iv`, `ks`, `separability`, and `temporal_score`
- temporal coverage and rare-bin signals
- score strategy, objective direction, and comparison-ready score
- objective components and penalties
- raw components, normalized components, and effective weights
- normalization mode and WoE shrinkage parameters
- `key_drivers`, `key_penalties`
- `selection_basis`
- `rationale_summary`

`export_binnings_json(...)` creates a single JSON artifact with:

- fit metadata and RiskBands version
- strategy, score strategy, normalization mode, shrinkage configuration
- missing policy and effective missing policy
- missing merge criterion and fallback when merge is enabled
- target, time column, fitted features and generation timestamp
- auditable score weights and effective score-weight profile
- per-feature binning tables, score details and audit-friendly summaries

`export_bundle(...)` creates a folder-oriented bundle with:

- `metadata.json`
- `binnings.json`
- friendly CSV outputs such as `summary.csv`, `score_table.csv`, `audit_table.csv`, and `report.csv`
- missing audit outputs such as `missing_profile.csv` and `missing_decision_log.csv` when available
- merge audit outputs such as `missing_merge_candidates.csv` when available
- `audit_report.html` by default, unless `include_audit_report=False`
- per-feature tables under `feature_tables/`
- parquet artifacts when the environment has parquet support available
- sampling metadata and `missing_sampling_diagnostics` when Spark sampled-to-pandas fit is used

`export_audit_report(path, title=None, dataset_name=None)` creates a standalone
HTML narrative report with embedded CSS and no external assets. It explains the
model configuration, variables, missing policies, missing merge decisions,
merge candidates, validation alerts, bundle inventory, and known limitations.

When Spark sampled-to-pandas fit is used for missing merge, the report and
bundle metadata carry the sampling caveat, source/sample row counts when
available, and diagnostics that help reviewers see whether source missing values
were represented in the sample.

The report is print-friendly and can be exported to PDF by the browser. Native
PDF export is not part of the public API in this release. The report organizes
evidence and technical decisions, but it does not replace independent formal
validation or constitute regulatory certification.

## Credit-Oriented Optimization

`optimize_bins(...)` now supports two explicit scoring strategies:

- `standard`
  - maximize-oriented
  - keeps the historical score based on positive components and penalties
  - `legacy` is accepted only as a compatibility alias
- `stable`
  - minimize-oriented
  - explicit stable objective with normalized components
  - from `2.0.0` onward, this is the only public name for the temporal objective

`stable` combines:

- temporal weighted variance of shrinked WoE
- adjacent window drift
- rank inversion penalty
- separation penalty
- entropy penalty
- PSI penalty

Default weights:

- `temporal_variance_weight=0.22`
- `window_drift_weight=0.18`
- `rank_inversion_weight=0.20`
- `separation_weight=0.20`
- `entropy_weight=0.08`
- `psi_weight=0.12`

Standard optimization remains composed of:

- base components:
  - `separability`
  - `iv`
  - `ks`
  - `temporal_score`
- penalties:
  - `rare_bin_count`
  - `coverage_ratio_min`
  - `event_rate_std_max`
  - `woe_std_max`
  - `bin_share_std_max`
  - `monotonic_break_period_count`
  - `ranking_reversal_period_count`

The final winner summary is stored in `objective_summary_`.

Interpretation:

- in `standard`, higher `objective_score` is better
- in `stable`, lower `objective_score` is better
- `objective_preference_score` keeps comparisons consistent across strategies

## `BinComparator`

Available from `riskbands.compare`.

Core methods:

- `fit_compare(...)`
- `candidate_audit_report()`
- `candidate_profile_summary()`
- `winner_summary()`

Compared profiles:

- best static candidate
- best temporal candidate
- best balanced candidate
- final selected candidate

## Examples

- [examples/temporal_stability/temporal_stability_example.py](../examples/temporal_stability/temporal_stability_example.py)
- [examples/temporal_stability/temporal_stability_example.ipynb](../examples/temporal_stability/temporal_stability_example.ipynb)
- [examples/pd_vintage_champion_challenger/pd_vintage_champion_challenger.py](../examples/pd_vintage_champion_challenger/pd_vintage_champion_challenger.py)
- [examples/pd_vintage_champion_challenger/pd_vintage_champion_challenger.ipynb](../examples/pd_vintage_champion_challenger/pd_vintage_champion_challenger.ipynb)
