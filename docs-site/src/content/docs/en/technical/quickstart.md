---
title: Quickstart
description: "Fit your first RiskBands object with the project's friendliest API and inspect score, audit, export, and plots in a few steps."
---

## The recommended flow today

For a new user, the simplest and most complete path is:

1. create a `RiskBands`
2. fit it with `fit(df, y="target", column="score", time_col="month")`
3. inspect `summary()`
4. open `score_table()` and `audit_table()`
5. export the auditable artifacts
6. use the public plots for temporal reading

```python
import numpy as np
import pandas as pd

from riskbands import RiskBands

rng = np.random.default_rng(0)
n = 800

df = pd.DataFrame({"score": rng.normal(size=n)})
df["month"] = rng.choice([202301, 202302, 202303, 202304], size=n)

proba = 0.20 + 0.15 * df["score"] + 0.02 * (df["month"] - 202301)
proba = np.clip(proba, 0.01, 0.99)
df["target"] = (rng.random(n) < proba).astype(int)

binner = RiskBands(
    strategy="supervised",
    max_n_bins=5,
    check_stability=True,
    missing_policy="standard",
    score_strategy="stable",
    normalization_strategy="absolute",
    woe_shrinkage_strength=35.0,
)

binner.fit(df, y="target", column="score", time_col="month")

score_bins = binner.transform(df["score"])
summary = binner.summary()
score_table = binner.score_table()
audit_table = binner.audit_table()

binner.export_binnings_json("artifacts/riskbands_binnings.json")
binner.export_bundle("artifacts/quickstart_run")

binner.plot_bad_rate_over_time(df, y="target", column="score", time_col="month")
binner.plot_bad_rate_heatmap(df, y="target", column="score", time_col="month")
binner.plot_bin_share_over_time(df, y="target", column="score", time_col="month")
binner.plot_score_components(column="score")
```

## Missing values

The default `missing_policy="standard"` preserves current behavior. When you
need to audit missing values explicitly, use `missing_policy="separate_bin"`.
When missing values must be blocked before binning, use
`missing_policy="forbid"`.

When missing should remain audited but be routed to a regular bin, use
`missing_policy="merge"` with `missing_merge_criterion="nearest_event_rate"` or
`missing_merge_criterion="nearest_woe"`.

These policies do not perform opaque imputation. In merge mode, the rule is
learned during `fit` and reused during `transform`, without retargeting from
application data.

For complete pandas and PySpark examples, see
[Missing policy](../missing-policy/).

## What to look at first

### `summary()`

The best first stop after fitting: bins, IV, score strategy, and temporal
warnings.

### `score_table()`

Short reading for final score, comparison score, objective direction, weights,
and the most relevant components.

### `audit_table()`

Consolidated view for auditable review: final cuts, score, coverage, rare bins,
reversals, and summarized rationale.

## When to use `stable`

For a new user, `stable` is usually the best public strategy to start with when
a temporal column exists, stability matters, and you want to balance separation
and robustness.

If you need to reproduce a historical behavior or compare against the previous
approach, use `standard`.

## Next steps

- [Missing policy](../missing-policy/)
- [Outputs and diagnostics](../outputs/)
- [Score and strategies](../score-strategy/)
- [API overview](../api-overview/)
- [Examples](../examples/)
