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

## What became friendlier

Without aggressive changes to the core, the public `Binner` API became closer
to familiar sklearn and pandas patterns:

- `fit(df, y="target", column="score")`
- `fit(df["score"], y=df["target"])`
- `transform(df)` or `transform(df["score"])`
- `fit_transform(...)`
- `summary()`
- `score_details()`
- `score_table()`
- `report()`
- `audit_table()`
- `diagnostics()`
- `binning_table()`
- `feature_binning_table()`
- `plot_bad_rate_over_time()`
- `plot_bad_rate_heatmap()`
- `plot_bin_share_over_time()`
- `plot_score_components()`
- `export_binnings_json()`
- `export_bundle()`

Friendlier configuration aliases were also added:

- `max_n_bins` as an alias for `max_bins`
- `monotonic_trend` as an alias for `monotonic`

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
| `BinComparator` | Champion/challenger comparison | Remains central when the problem is choosing between multiple candidates |

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

Today the API exposes two explicit strategies:

- `standard`
  Keeps the historical maximization-oriented score. `legacy` remains accepted
  only as a compatibility alias.
- `stable`
  Introduces the temporal-robustness-oriented minimization objective.

## Missing values

`missing_policy` accepts:

- `standard`: compatible default with the current behavior
- `separate_bin`: opt-in explicit `Missing` bin
- `forbid`: error during `fit` or `transform` if selected features contain missing values

`separate_bin` does not perform opaque imputation; it makes missing values
explicit and auditable. Merge policies are not part of the public contract yet.

Dedicated guide: [Missing policy](../missing-policy/).

After `fit`, inspect `missing_profile_` and `missing_decision_log_` to see
volume, share, event rate, and the decision taken per variable. These fields
are also persisted by `export_bundle(...)`.

Example:

```python
binner = RiskBands(
    strategy="supervised",
    check_stability=True,
    time_col="month",
    missing_policy="separate_bin",
    score_strategy="stable",
    score_weights={
        "temporal_variance_weight": 0.22,
        "window_drift_weight": 0.18,
        "rank_inversion_weight": 0.20,
        "separation_weight": 0.20,
        "entropy_weight": 0.08,
        "psi_weight": 0.12,
    },
    normalization_strategy="absolute",
    woe_shrinkage_strength=40.0,
)
```

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
