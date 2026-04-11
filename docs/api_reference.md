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

- `1.0.0`

## `Binner`

Primary constructor of the library.

Common parameters:

- `strategy`: `"supervised"` or `"unsupervised"` for numeric variables
- `max_bins`: default upper limit for bins
- `min_event_rate_diff`: minimum event-rate gap used during refinement
- `monotonic`: `"ascending"`, `"descending"`, or `None`
- `check_stability`: enables temporal checks in the flow
- `use_optuna`: enables hyperparameter search for `strategy="supervised"`
- `time_col`: period column used by temporal diagnostics
- `strategy_kwargs`: strategy-specific parameters

Common methods:

- `fit(X, y, time_col=None)`
- `transform(X, return_woe=False)`
- `fit_transform(X, y, **fit_params)`
- `stability_over_time(X, y, time_col, fill_value=None)`
- `temporal_bin_diagnostics(X, y, time_col, dataset_name=None, ...)`
- `temporal_variable_summary(X=None, y=None, diagnostics=None, time_col=None, ...)`
- `variable_audit_report(X=None, y=None, time_col=None, diagnostics=None, summary=None, ...)`
- `plot_event_rate_stability(pivot=None, **kwargs)`
- `save_report(path)`
- `describe_schema()`
- `get_bin_mapping(column)`

Main attributes after `fit`:

- `bin_summary`
- `iv_`
- `iv_by_variable_`
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
- objective components and penalties
- `key_drivers`, `key_penalties`
- `selection_basis`
- `rationale_summary`

## Credit-Oriented Optimization

`optimize_bins(...)` uses a simple auditable score composed of:

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

