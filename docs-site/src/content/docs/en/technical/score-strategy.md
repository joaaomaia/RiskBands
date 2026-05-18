---
title: "Score and strategies"
description: "How to think about `strategy`, `score_strategy`, `stable`, `normalization_strategy`, and `woe_shrinkage_strength` in RiskBands."
---

## Two strategy levels

In RiskBands, it helps to separate two decisions:

1. `strategy`
   Decides how the binning is built.
2. `score_strategy`
   Decides how candidates are evaluated and compared.

## `strategy`

Today the API mainly exposes:

- `supervised`
- `unsupervised`

In general:

- use `supervised` when the target is available and you want cuts guided by separation;
- use `unsupervised` when you want a simpler structure or an internal comparison baseline.

## `score_strategy`

The valid public values now are:

- `standard`
- `stable`

`standard` is the canonical name of the historical maximization-oriented score.
`legacy` remains accepted only as a compatibility alias.

## When to use `stable`

`stable` is the preferred strategy when the real question is:

> among plausible candidates, which one best balances separation and temporal robustness?

It is especially useful when you care about:

- temporal variance of WoE
- drift between windows
- ranking inversions between bins
- PSI
- enough separation without sacrificing stability

In practical terms, `stable` is minimization-oriented:

- lower `objective_score` is better
- higher `objective_preference_score` still helps with consolidated comparisons

## When to use `standard`

`standard` remains useful when you want to:

- reproduce the project's historical reading
- compare against previous behavior
- use a score closer to the older formulation based on positive components minus penalties

## `normalization_strategy`

Today the supported value is:

- `absolute`

It exists to put objective components on a comparable scale even when only one
candidate is being evaluated.

In practice, it:

- avoids summing incompatible magnitudes
- helps read normalized components in `score_details()`
- keeps the objective usable with and without Optuna

## `woe_shrinkage_strength`

This parameter controls how much temporal WoE is pulled toward a more stable
reference before entering score components.

Practical intuition:

- higher value: more smoothing, less sensitivity to noise and small bins
- lower value: more fidelity to observed behavior, with greater sensitivity to oscillation

When to increase it:

- small datasets
- rare bins
- short or noisy time series

When to reduce it:

- larger samples
- well-supported bins
- need to capture finer temporal variation

## Complete example

```python
from riskbands import RiskBands

binner = RiskBands(
    strategy="supervised",
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
    woe_shrinkage_strength=35.0,
    check_stability=True,
)
```

## How to think about separation versus stability

A practical rule:

- if you only maximize static IV, you may choose a temporally fragile candidate;
- if you only maximize stability, you may choose an almost useless candidate;
- `stable` tries to balance these two forces explicitly.

## Next steps

- [Outputs and diagnostics](../outputs/)
- [API overview](../api-overview/)
- [Quickstart](../quickstart/)
