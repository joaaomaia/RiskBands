# RiskBands

<p align="center">
  <img src="./imgs/social_preview.png" alt="RiskBands Banner" width="600"/>
</p>

Interpretable binning for credit risk, PD, and scorecard workflows, with explicit attention to temporal stability.

## What RiskBands Solves

Static binning can look strong in development and still become hard to defend once vintages shift. RiskBands helps teams evaluate bins not only by discrimination, but also by how stable, auditable, and structurally robust they remain over time.

The library stays intentionally focused on the binning layer:

- supervised and unsupervised numeric binning
- categorical binning with rare-category handling
- temporal diagnostics by variable, bin, and period
- candidate comparison for static, temporal, and balanced profiles
- auditable reporting of the final selection rationale

It is not a full PD modeling framework. It is the binning and stability layer that can sit inside a broader credit workflow.

## Why Temporal Stability Matters

A purely static binning process optimizes separation on the development sample. In credit risk, that is often not enough. Period mix, origination strategy, and data quality can drift, so a binning that looks excellent in train may degrade in later vintages.

RiskBands is designed for cases where we need to ask:

- do the bins keep their ordering over time?
- do event rates stay separated across periods?
- are some bins becoming sparse or structurally fragile?
- can we explain why one candidate won beyond raw IV?

## Installation

```bash
pip install .
```

For development:

```bash
git clone https://github.com/joaaomaia/RiskBands.git
cd RiskBands
pip install -e .[dev]
```

## Main API

```python
from riskbands import Binner, BinComparator
from riskbands.temporal_stability import ks_over_time
```

The public package now exposes:

- package: `riskbands`
- main class: `Binner`

## Main Workflow

1. Fit the binner with `Binner(...).fit(X, y, time_col=...)`.
2. Transform the feature set with `transform(...)`.
3. Build temporal pivots with `stability_over_time(...)`.
4. Open the detailed diagnostics with `temporal_bin_diagnostics(...)`.
5. Summarize the variable-level behavior with `temporal_variable_summary(...)`.
6. Consolidate the audit trail with `variable_audit_report(...)`.
7. Compare candidates with `BinComparator` when doing champion/challenger analysis.

## Quick Example

```python
import numpy as np
import pandas as pd

from riskbands import Binner

rng = np.random.default_rng(0)
n = 800

X = pd.DataFrame({"score": rng.normal(size=n)})
X["month"] = rng.choice([202301, 202302, 202303, 202304], size=n)

proba = 0.20 + 0.15 * X["score"] + 0.02 * (X["month"] - 202301)
proba = np.clip(proba, 0.01, 0.99)
y = pd.Series((rng.random(n) < proba).astype(int), name="target")

binner = Binner(
    strategy="supervised",
    check_stability=True,
    monotonic="ascending",
    min_event_rate_diff=0.03,
)

binner.fit(X, y, time_col="month")

diagnostics = binner.temporal_bin_diagnostics(
    X,
    y,
    time_col="month",
    dataset_name="train",
)
summary = binner.temporal_variable_summary(
    diagnostics=diagnostics,
    time_col="month",
)
audit_report = binner.variable_audit_report(
    X,
    y,
    time_col="month",
    dataset_name="train",
)

print(summary[["variable", "temporal_score", "alert_flags"]])
print(audit_report[["variable", "objective_score", "rationale_summary"]])
```

## Examples

- [examples/temporal_stability/temporal_stability_example.py](examples/temporal_stability/temporal_stability_example.py)
  Quickstart for the temporal workflow.
- [examples/pd_vintage_champion_challenger/pd_vintage_champion_challenger.py](examples/pd_vintage_champion_challenger/pd_vintage_champion_challenger.py)
  Credit-oriented champion/challenger example with vintages.
- [examples/README.md](examples/README.md)
  Map of the example set.

## Breaking Change History

This codebase has gone through two deliberate API simplifications:

- `NASABinning` -> `RiskBands`
- `RiskBandsBinner` -> `Binner`

The current official constructor is `Binner`.

## Migration

If you were already on the `riskbands` namespace but still used the longer class name:

```python
# before
from riskbands import RiskBandsBinner

# now
from riskbands import Binner
```

If you still import `nasabinning`, you also need to migrate to `riskbands`.

See [docs/migration.md](docs/migration.md) for the full migration notes.

## Documentation

- [docs/index.md](docs/index.md)
- [docs/api_reference.md](docs/api_reference.md)
- [docs/migration.md](docs/migration.md)

## Validation

```bash
pytest -q --basetemp .pytest_tmp
python -m build
```

CI is defined in [tests.yml](.github/workflows/tests.yml).

## License

MIT. See [LICENSE](LICENSE).
