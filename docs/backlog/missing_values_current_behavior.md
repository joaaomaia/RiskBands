# Missing values current behavior

This internal note records the RiskBands v2.1.0 missing-values behavior frozen by Sprint A tests. It is a handoff document for a future implementation sprint and does not describe a public `missing_policy` API.

## Sprint A scope

Sprint A formalizes the current behavior through tests and internal documentation only. It does not change production semantics, does not add imputation, does not add a missing merge rule, and does not add a public missing-values policy.

## Diagnostic summary

The current behavior is asymmetric by dtype:

- Numeric missing values are generally observable as a `Missing` transformed label and as a missing profile row.
- Numeric missing rows are not consistently visible in `bin_summary`.
- Categorical missing values are converted to an internal `_MISSING_` token, but that token can map to an ordinary categorical/default bin.
- PySpark numeric paths explicitly map `NULL` and numeric `NaN` to `Missing`.
- PySpark categorical nulls follow the learned categorical mapping for `_MISSING_`.
- Bundles persist existing profile and validation evidence, but have no dedicated missing policy or decision-log schema.

## Numeric pandas behavior

In the supervised numeric pandas path, `np.nan` transforms to the label `Missing` in the current behavior. Sprint A tests assert this with a deterministic synthetic dataset.

`fit_profile_` includes a row where:

- `bin_label == "Missing"`
- `is_missing_bin == True`
- `is_regular_bin == False`
- `n`, `events`, `event_rate`, and `share` match the observed missing rows

This makes numeric missing auditable through profiles today.

## Categorical pandas behavior

The categorical path normalizes missing values through `CategoricalBinning.missing_token_`, currently `_MISSING_`. That token is a category value used by the categorical learner/mapping.

Current behavior does not guarantee a separate missing bin. In the Sprint A test dataset:

- `_MISSING_` is present in `get_bin_mapping("grade")`.
- `_MISSING_` maps to an ordinary categorical bin.
- `_UNKNOWN_` remains observable as a separate token and maps to its own current default/ordinary bin in the test dataset.
- `fit_profile_` has no row marked `is_missing_bin=True` for categorical missing.
- The profile row receiving missing observations is still marked as a regular bin.

This is deterministic, but it is not separately auditable as an explicit missing risk group.

## Numeric Spark behavior

For supervised numeric Spark transform, RiskBands builds Spark-native expressions. The current expression checks:

- `isNull()`
- `isnan()` when Spark supports the expression for the column

Values matching those conditions map to the literal label `Missing`. Sprint A tests cover both Spark `NULL` and numeric `NaN` and assert that transform returns a PySpark DataFrame.

## Categorical Spark behavior

For categorical Spark transform, `NULL` maps to:

```text
mapping.get("_MISSING_", default_bin)
```

The Spark path therefore mirrors the learned pandas categorical mapping. It does not create a literal `Missing` bin unless the learned mapping already points `_MISSING_` to such a label.

## Profiles and validation

Existing profiles include:

- `variable`
- `bin_id`
- `bin_label`
- `bin_order`
- `n`
- `events`
- `non_events`
- `event_rate`
- event-rate confidence interval fields
- `share`
- `woe`
- `iv_component`
- `is_missing_bin`
- `is_special_bin`
- `is_regular_bin`

`fit(validate=True)` creates `fit_validation_report_` and aliases it to `validation_report_`.

`transform(validate=True)` creates `application_profile_` and `transform_validation_report_`, then aliases the transform report to `validation_report_`. Sprint A tests assert that the original `fit_validation_report_` remains available after transform validation.

For Spark validation, profile rows are collected after Spark aggregation by variable/bin label. Sprint A tests guard `DataFrame.toPandas()` during transform validation to confirm that the validation path is collecting bounded aggregate profile rows rather than the full application DataFrame.

## bin_summary visibility

`bin_summary` is filtered to exclude technical labels such as `total`, `special`, and `missing`. As a result, numeric missing can be present in transform output and profiles while absent from the fitted bin table. Sprint A tests intentionally document this as current behavior, not as a final desired state.

For categorical missing, the receiving ordinary bin appears in `bin_summary`, but the row is not identified as a missing bin.

## Bundle behavior

Current bundles preserve existing profile and validation fields, including:

- `fit_profile`
- `reference_profile`
- `application_profile`
- `fit_validation_report`
- `transform_validation_report`
- `validation_report`

Sprint A tests assert that numeric `Missing` profile rows survive bundle export/load through these existing fields.

The bundle currently does not include:

- `missing_policy`
- `effective_missing_policy`
- `missing_decision_log`
- `missing_profile`

Bundle loading restores metadata and artifacts for audit workflows; it does not reconstruct a callable estimator from only the bundle.

## Gaps for Sprint B

- Decide the public default for a future `missing_policy`.
- Decide whether `separate_bin` should be the immediate default or an opt-in compatibility mode.
- Decide whether `forbid` enters the first implementation sprint.
- Decide how categorical missing should become separately auditable without silently breaking users who rely on the current `_MISSING_` to ordinary-bin behavior.
- Decide whether missing should appear in `bin_summary`, a separate profile, or both.
- Define bundle schema names for policy metadata, missing profiles, and decision logs.
- Keep old bundles loadable without rewriting them.
- Keep pandas and Spark transform semantics equivalent for supported dtypes.

## References

This note is based on the Sprint A goal references under:

```text
docs/goals/riskbands-missing-values-sprint-a-goal/reference/
```

The broader product rationale is recorded in:

```text
docs/NOTA_TECNICA_Backlog_Missing_Values_Auditavel_RiskBands.txt
```

The technical note recommends treating missing values as auditable binning behavior rather than opaque imputation. Sprint A only records the baseline needed before that future design work.
