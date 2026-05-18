---
title: "Missing policy"
description: "How to use standard, separate_bin, and forbid to handle missing values with an auditable trail in RiskBands."
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

`legacy` may appear in old metadata for compatibility, but it is not a new
recommendation. The current canonical name is `standard`.

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
- `transform(validate=True)`;
- `missing_policy="forbid"` producing a clear error;
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

`missing_profile_` shows volume, share, events, event rate, backend, context,
and whether the row represents a missing bin. `missing_decision_log_` records
the action taken per variable.

## Bundle and reporting

`export_bundle(...)` persists the missing-values trail:

- `missing_policy`
- `effective_missing_policy`
- `missing_profile`
- `missing_decision_log`

```python
from riskbands.reporting import load_bundle

binner.export_bundle("riskbands_bundle")
bundle = load_bundle("riskbands_bundle")

print(bundle["missing_policy"])
print(bundle["missing_profile"])
```

Old bundles without these fields continue to load as `standard`.

## What is not implemented

This page documents the current contract. It does not announce new features.

There are not yet:

- auditable merge policies to merge the missing bin into another bin;
- intelligent imputation inside RiskBands;
- automatic behavioral similarity for missing values;
- fully distributed statistical fitting in Spark.

RiskBands helps make the decision defensible and auditable, but it does not
automatically guarantee regulatory compliance.
