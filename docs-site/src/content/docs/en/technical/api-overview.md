---
title: "API overview"
description: "Map of the public RiskBands surface, focused on onboarding, audit, and friendly temporal reading."
---

## Recommended entry point

In most cases, the ideal flow for a new user is:

1. instantiate `RiskBands`
2. run `fit(...)`
3. inspect `summary()`, `score_table()`, and `audit_table()`
4. apply `transform(...)`
5. export auditable artifacts
6. use the public plots for temporal reading

## Main public surface

```python
from riskbands import RiskBands, Binner, BinComparator
from riskbands.temporal_stability import (
    ks_over_time,
    psi_over_time,
    temporal_separability_score,
)
```

`RiskBands` is the preferred name. `Binner` remains available for
compatibility, and `RiskBands is Binner` remains true.

## Core blocks

| Component | Role in the flow | Why it matters |
| --- | --- | --- |
| `RiskBands` / `Binner` | Main entry point | Fits, transforms, summarizes, exports, and plots without requiring internal structures |
| `summary()` | Short post-fit summary | Helps quickly understand bins, IV, and score |
| `score_table()` | Short objective explanation | Exposes final score, weights, and the most relevant components |
| `audit_table()` | Consolidated auditable review | Combines cuts, score, penalties, coverage, and rationale |
| `diagnostics()` | Detailed temporal reading | Opens stability by bin or by variable |
| `export_binnings_json()` | Single JSON artifact | Makes versioning and governance easier |
| `export_bundle()` | Complete audit package | Generates JSON, CSV, and feature-level tables |
| `BinComparator` | Champion/challenger comparison | Helps choose between multiple candidates |

## Recommended single-candidate flow

```python
binner = RiskBands(
    strategy="supervised",
    score_strategy="stable",
    max_n_bins=5,
    check_stability=True,
    missing_policy="standard",
)

binner.fit(df, y="target", column="score", time_col="month")

score_bins = binner.transform(df["score"])
summary = binner.summary()
score_table = binner.score_table()
audit_table = binner.audit_table()

binner.export_binnings_json("artifacts/riskbands_binnings.json")
binner.export_bundle("artifacts/run_2026_04_14")
```

## Score strategies

The API exposes two explicit strategies:

- `standard`: the historical maximization-oriented score. `legacy` remains
  accepted only as a compatibility alias.
- `stable`: the temporal-robustness-oriented minimization objective.

## Missing values

`missing_policy` accepts:

- `standard`: compatible default with the current behavior
- `separate_bin`: opt-in explicit `Missing` bin
- `forbid`: error during `fit` or `transform` if selected features contain missing values
- `merge`: opt-in pandas routing from the missing group to the closest regular bin learned during `fit`

`merge` requires `missing_merge_criterion="nearest_event_rate"` or
`missing_merge_criterion="nearest_woe"`. The first uses absolute event-rate
distance; the second uses absolute WoE distance. `missing_merge_fallback`
accepts `separate_bin` or `raise` for missing values that appear during
`transform` without a fit-time decision.

These policies do not perform opaque imputation. In merge mode, `transform(...)`
uses only the decision learned during `fit` and does not learn a new rule from
application data.

After `fit`, inspect `missing_profile_`, `missing_decision_log_`,
`missing_merge_candidates_`, and `missing_merge_map_` to review volume, share,
event rate, criterion, candidates, distances, and learned destination.

Example:

```python
binner = RiskBands(
    strategy="supervised",
    check_stability=True,
    time_col="month",
    missing_policy="merge",
    missing_merge_criterion="nearest_woe",
    missing_merge_fallback="separate_bin",
    score_strategy="stable",
)
```

Dedicated guide: [Missing policy](../missing-policy/).

## What to inspect next

After the first `fit`, the most useful trio is usually:

- `summary()` for a short reading
- `score_table()` to understand score and weights
- `audit_table()` to open the auditable review

## Next steps

- [Quickstart](../quickstart/)
- [Outputs and diagnostics](../outputs/)
- [Missing policy](../missing-policy/)
- [Examples](../examples/)
