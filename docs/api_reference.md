# API Reference

## Public Surface

```python
from riskbands import (
    Binner,
    BinComparator,
    temporal_separability_score,
    ks_over_time,
    psi_over_time,
)
```

Current version:

- `2.0.2`

## `Binner`

Primary constructor of the library.

Common parameters:

- `strategy`: `"supervised"` or `"unsupervised"` for numeric variables
- `max_bins`: default upper limit for bins
- `max_n_bins`: sklearn/optbinning-friendly alias for `max_bins`
- `min_event_rate_diff`: minimum event-rate gap used during refinement
- `monotonic`: `"ascending"`, `"descending"`, or `None`
- `monotonic_trend`: alias for `monotonic`
- `check_stability`: enables temporal checks in the flow
- `use_optuna`: enables hyperparameter search for `strategy="supervised"`
- `time_col`: period column used by temporal diagnostics
- `score_strategy`: `"legacy"` or `"stable"`
- `score_weights`: optional weights for `stable`
- `normalization_strategy`: currently `absolute` for standalone-safe normalization
- `woe_shrinkage_strength`: shrink intensity applied before temporal scoring
- `objective_kwargs`: advanced score configuration override
- `strategy_kwargs`: strategy-specific parameters
  - when `use_optuna=True`, `strategy_kwargs` can also carry search controls such as `n_trials` and `sampler_seed`

Common methods:

- `fit(X, y=None, target=None, column=None, columns=None, time_col=None, ...)`
- `transform(X, column=None, columns=None, return_woe=False, return_type="auto")`
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
- `export_bundle(path)`
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
- `save_report("...xlsx")` requires an XLSX writer engine such as `openpyxl` or `xlsxwriter`.

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
- target, time column, fitted features and generation timestamp
- auditable score weights and effective score-weight profile
- per-feature binning tables, score details and audit-friendly summaries

`export_bundle(...)` creates a folder-oriented bundle with:

- `metadata.json`
- `binnings.json`
- friendly CSV outputs such as `summary.csv`, `score_table.csv`, `audit_table.csv`, and `report.csv`
- per-feature tables under `feature_tables/`
- parquet artifacts when the environment has parquet support available

## Credit-Oriented Optimization

`optimize_bins(...)` now supports two explicit scoring strategies:

- `legacy`
  - maximize-oriented
  - keeps the historical score based on positive components and penalties
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

Legacy optimization remains composed of:

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

- in `legacy`, higher `objective_score` is better
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

