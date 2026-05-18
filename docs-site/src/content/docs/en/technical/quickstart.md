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

These policies do not perform opaque imputation and do not include merge
policies.

For complete pandas and PySpark examples, see
[Missing policy](../missing-policy/).

## Why this flow is friendlier

It follows familiar conventions:

- `fit(...)`
- `transform(...)`
- `fit_transform(...)`
- pandas `DataFrame` and `Series` as the first option
- short tables for notebooks before opening full detail

It also avoids requiring you to assemble pivots, bundles, or internal
dictionaries at the beginning.

## What to look at first

### `summary()`

This is the best first stop after fitting.

Use it when you want to answer quickly:

- how many bins were kept?
- what was the IV?
- which score strategy is active?
- are there relevant temporal warnings?

### `score_table()`

This is the shortest reading for explaining the objective.

It helps inspect:

- final score
- comparison score
- objective direction
- weights used
- the most relevant components and penalties

### `audit_table()`

This is the consolidated view for auditable review.

It combines:

- final cuts
- score
- coverage
- rare bins
- reversals
- summarized rationale

## When to use `stable`

For a new user, `stable` is usually the best public strategy to start with
when:

- a temporal column exists
- stability really matters
- you want to balance separation and robustness

If you need to reproduce a more historical behavior or compare against the
previous approach, use `standard`.

## Next steps

- [Missing policy](../missing-policy/)
- [Outputs and diagnostics](../outputs/)
- [Score and strategies](../score-strategy/)
- [API overview](../api-overview/)
- [Examples](../examples/)
