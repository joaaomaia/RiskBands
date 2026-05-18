---
title: "RiskBands documentation"
description: "Official RiskBands documentation for temporal-robust binning, stable scoring, friendly onboarding, and credit-ready workflows."
template: splash
hero:
  title: RiskBands
  tagline: >-
    Binning for credit risk with a focus on temporal robustness. RiskBands helps
    move from a static IV reading to a more defensible decision across
    separation, stability, and auditability.
  actions:
    - text: Get started
      link: ./technical/quickstart/
      icon: right-arrow
    - text: Understand the stable score
      link: ./technical/score-strategy/
      icon: right-arrow
      variant: minimal
features:
  - title: Quick start
    description: Installation, a minimal first example, and the recommended `RiskBands` workflow in a sklearn/pandas style.
    link: ./technical/quickstart/
  - title: Score strategy
    description: Understand `standard` vs `stable`, when to use each one, and how to think about separation versus temporal robustness.
    link: ./technical/score-strategy/
  - title: Readable outputs
    description: Learn how to interpret `summary()`, `report()`, `score_details()`, `diagnostics()`, and `binning_table()`.
    link: ./technical/outputs/
  - title: Auditable missing values
    description: Use `standard`, `separate_bin`, or `forbid` without opaque imputation and with a persisted audit trail in bundles.
    link: ./technical/missing-policy/
  - title: API overview
    description: See the public surface for onboarding, audit, temporal reading, exports, and public plots.
    link: ./technical/api-overview/
  - title: Examples
    description: Follow scripts and notebooks for quickstart, benchmark, audit, missing policy, and friendly API usage.
    link: ./technical/examples/
  - title: Release notes
    description: Review the main public package and documentation milestones without changing release status.
    link: ./reference/release-notes/
---

## What RiskBands is

RiskBands is a Python library for building, comparing, and auditing binning
candidates when the real question is not only "which cut has the highest IV?",
but:

> which solution remains more defensible when time becomes part of the analysis?

It was designed for cases such as:

- PD models
- credit scorecards
- vintage or cohort analysis
- variables with temporal drift
- structures with rare bins, fragile coverage, or ranking reversals

## Why use it

`OptimalBinning` already solves static cuts very well. RiskBands helps decide
whether that cut is still the best answer when behavior is opened by period.

In practice, the project adds:

- temporal diagnostics by variable, bin, and period
- a temporal-robustness-oriented score with the `stable` strategy
- candidate comparison through `BinComparator`
- auditable reports explaining why a candidate won

## Recommended path for a new user

1. Install the Python package.
2. Run the [Quickstart](./technical/quickstart/).
3. Read [Score and strategies](./technical/score-strategy/) to understand `stable`.
4. Read [Missing policy](./technical/missing-policy/) if your data contains missing values.
5. Use [Outputs and diagnostics](./technical/outputs/) to learn how to read the result.
6. Continue with [Examples](./technical/examples/) or the methodology pages in the pt-BR documentation.

## Minimal flow

```python
from riskbands import RiskBands

binner = RiskBands(
    strategy="supervised",
    score_strategy="stable",
    max_n_bins=5,
    check_stability=True,
    missing_policy="standard",
)

binner.fit(df, y="target", column="score", time_col="month")
summary = binner.summary()
score_details = binner.score_details()
```

## What makes the `stable` score different

`stable` does not choose the best candidate only by static IV.

It combines:

- temporal variance of shrunken WoE
- drift between windows
- ranking inversions between bins
- separation
- entropy
- PSI

All of these are combined in a comparable minimization-oriented objective.

## Next steps

- Want to start using it? Go to [Quickstart](./technical/quickstart/).
- Need to audit missing values? Go to [Missing policy](./technical/missing-policy/).
- Want to understand the recommended strategy? Go to [Score and strategies](./technical/score-strategy/).
- Want the public API map? Go to [API overview](./technical/api-overview/).
