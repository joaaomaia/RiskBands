# RiskBands Docs

Entry point for the project documentation.

## Recommended Flow

1. Fit `Binner(...).fit(X, y, time_col=...)`.
2. Transform the data with `transform(...)`.
3. Generate the temporal pivot with `stability_over_time(...)`.
4. Inspect the detailed diagnostics with `temporal_bin_diagnostics(...)`.
5. Summarize stability with `temporal_variable_summary(...)`.
6. Consolidate the rationale with `variable_audit_report(...)`.
7. Compare candidates with `BinComparator` when doing champion/challenger.

## Quick Navigation

- [README.md](../README.md)
  Project overview, installation, quickstart, and positioning.
- [docs/api_reference.md](api_reference.md)
  Main API contract and public package surface.
- [docs/migration.md](migration.md)
  Breaking migration guide for users coming from `NASABinning`.
- [examples/README.md](../examples/README.md)
  Map of the main examples.
- [examples/temporal_stability/temporal_stability_example.py](../examples/temporal_stability/temporal_stability_example.py)
  Minimal temporal quickstart.
- [examples/pd_vintage_champion_challenger/pd_vintage_champion_challenger.py](../examples/pd_vintage_champion_challenger/pd_vintage_champion_challenger.py)
  Credit-risk / PD anchor example with vintages.

## What to Look For in Credit Work

The most relevant components for PD and interpretable scorecard workflows are:

- `temporal_separability_score(...)`
- `temporal_bin_diagnostics(...)`
- `temporal_variable_summary(...)`
- `variable_audit_report(...)`
- `BinComparator` with `candidate_profile_summary()` and `winner_summary()`

## Local Validation

```bash
pytest -q --basetemp .pytest_tmp
```

Light CI workflow:

- [tests.yml](../.github/workflows/tests.yml)

