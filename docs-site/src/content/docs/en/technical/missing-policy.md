---
title: "Missing policy"
description: "How to use standard, separate_bin, forbid, and merge to handle missing values with an auditable trail in RiskBands."
---

## Core idea

In credit risk, missing values can carry their own signal. A missing field may
reflect data source, channel, operational policy, or a change in capture. For
that reason, silently applying `fillna(...)` before binning can hide a relevant
decision.

`missing_policy` makes that decision explicit:

```python
from riskbands import RiskBands

binner = RiskBands(missing_policy="separate_bin")
```

## Policies

| Policy | What it does | When to use |
| --- | --- | --- |
| `standard` | Preserves the current compatible behavior. | Reproducing existing flows and compatibility. |
| `separate_bin` | Creates an explicit `Missing` bin for missing values in selected features. | Auditable analysis of missing values as their own group. |
| `forbid` | Fails during `fit` or `transform` when missing values are found. | Governance that requires upstream treatment before binning. |
| `merge` | Learns a regular destination bin for the missing group during `fit`. | When missing should remain audited but be routed to the closest bin. |

`legacy` may appear in old metadata for compatibility, but it is not a new
recommendation. The current canonical name is `standard`.

## Auditable merge

`missing_policy="merge"` is opt-in and requires an explicit criterion:

```python
binner = RiskBands(
    missing_policy="merge",
    missing_merge_criterion="nearest_event_rate",
    missing_merge_fallback="separate_bin",
)
```

```python
binner = RiskBands(
    missing_policy="merge",
    missing_merge_criterion="nearest_woe",
    missing_merge_fallback="raise",
)
```

`nearest_event_rate` selects the regular bin with the smallest absolute event-rate
distance from the missing group during fit. `nearest_woe` uses the smallest
absolute WoE distance from the same fit profile.

Merge is not opaque imputation. The decision is stored in
`missing_decision_log_`, candidates are stored in `missing_merge_candidates_`,
and the learned routing map is stored in `missing_merge_map_`. `transform(...)`
uses only the fit-time decision; it does not learn a new rule from application
data.

In Spark, v2.4.0 supports the controlled sampled-to-pandas `fit` path and
applies the learned decision during `transform` with native Spark expressions
and `return_woe=False`. This is not Spark-native full fit: review the sampling
metadata, `source_profile_`, and `missing_sampling_diagnostics_` when using
`fit(validate=True)`.

Compare merge against `separate_bin` before accepting the decision. The
[`missing_policy_comparison_demo.py`](https://github.com/joaaomaia/RiskBands/blob/main/examples/missing_policy/missing_policy_comparison_demo.py)
script builds a table with IV, number of bins, missing event rate, action,
selected bin, distance, candidates, fallback, and a simple period metric. The
[`credit_risk_missing_merge_demo.py`](https://github.com/joaaomaia/RiskBands/blob/main/examples/missing_policy/credit_risk_missing_merge_demo.py)
script shows the same flow on synthetic credit data with `bureau_score`,
`income`, `internal_rating`, `channel`, `product`, `vintage`, and `target`.

## pandas example

The complete script is available at
[`examples/missing_policy/missing_policy_pandas_demo.py`](https://github.com/joaaomaia/RiskBands/blob/main/examples/missing_policy/missing_policy_pandas_demo.py).

```python
import numpy as np
import pandas as pd

from riskbands import RiskBands

df = pd.DataFrame(
    {
        "score": [410.0, 450.0, np.nan, 620.0, 710.0] * 6,
        "rating": ["A", "B", None, "C", "D"] * 6,
        "target": [0, 0, 1, 1, 1] * 6,
    }
)

binner = RiskBands(
    max_bins=4,
    min_event_rate_diff=0.0,
    force_categorical=["rating"],
    missing_policy="separate_bin",
)

binner.fit(df, y="target", columns=["score", "rating"], validate=True)
df_binned = binner.transform(df[["score", "rating"]], validate=True)

print(df_binned.head())
print(binner.missing_profile_)
print(binner.missing_decision_log_)
```

Run locally:

```bash
python examples/missing_policy/missing_policy_pandas_demo.py
```

## PySpark example

PySpark is an optional extra. The base installation does not install Spark.

```bash
pip install "riskbands[spark]"
```

The complete script is available at
[`examples/missing_policy/missing_policy_pyspark_demo.py`](https://github.com/joaaomaia/RiskBands/blob/main/examples/missing_policy/missing_policy_pyspark_demo.py).

It uses:

- a small local `SparkSession` with `local[2]`;
- `spark.sql.shuffle.partitions=2`;
- a small synthetic dataset;
- `missing_policy="separate_bin"`;
- the Spark sampled-to-pandas path for `missing_policy="merge"` when the Spark
  extra is available;
- `transform(validate=True)`;
- `missing_policy="forbid"` producing a clear error;
- sampling caveats for Spark missing merge;
- no UDF.

```bash
python examples/missing_policy/missing_policy_pyspark_demo.py
```

If PySpark is not installed, the example prints how to install the extra and
exits without making Spark a base dependency.

## What to inspect

After `fit(...)`, look at:

- `missing_policy_`
- `effective_missing_policy_`
- `missing_profile_`
- `missing_decision_log_`
- `fit_profile_`, `reference_profile_`, and `application_profile_` when
  validation is enabled.
- `source_profile_` and `missing_sampling_diagnostics_` when Spark fit with
  missing merge uses sampled-to-pandas.

`missing_profile_` shows volume, share, events, event rate, backend, context,
and whether the row represents a missing bin. `missing_decision_log_` records
the action taken per variable.

## Bundle and reporting

`export_bundle(...)` persists the missing-values trail:

- `missing_policy`
- `effective_missing_policy`
- `missing_profile`
- `missing_decision_log`
- `missing_merge_criterion`
- `missing_merge_fallback`
- `missing_merge_candidates`
- `missing_merge_map`
- `missing_sampling_diagnostics` when Spark sampled-to-pandas creates sampling
  diagnostics

```python
from riskbands.reporting import load_bundle

binner.export_bundle("riskbands_bundle")
bundle = load_bundle("riskbands_bundle")

print(bundle["missing_policy"])
print(bundle["missing_profile"])
```

Old bundles without these fields continue to load as `standard`.

## What is not implemented

This page documents the current contract. There are not yet:

- `temporal_stable` as a merge criterion;
- `monotonic_neighbor` as a merge criterion;
- merge criteria beyond `nearest_event_rate` and `nearest_woe`;
- Spark-native full fit for missing merge;
- Spark `return_woe=True`;
- intelligent imputation inside RiskBands;
- fully distributed statistical fitting in Spark.

RiskBands helps make the decision defensible and auditable, but it does not
automatically guarantee regulatory compliance.
