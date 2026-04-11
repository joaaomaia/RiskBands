# Migration

## Breaking Change

The rename from `NASABinning` to `RiskBands` is complete in `1.0.0`.
This same release line also simplifies the main constructor name from `RiskBandsBinner` to `Binner`.

## What Changed

- the project name is now `RiskBands`
- the distribution name is now `riskbands`
- the only supported package namespace is `riskbands`
- the main public class is now `Binner`
- internal modules now live under `riskbands/`

## Old Imports Removed

These imports no longer work:

```python
import nasabinning
from nasabinning import NASABinner
from nasabinning.compare import BinComparator
from nasabinning.reporting import save_binner_report
```

## How to Migrate

If you are coming from the old project name:

```python
# before
from nasabinning import NASABinner
from nasabinning.compare import BinComparator

binner = NASABinner(check_stability=True)
```

```python
# after
from riskbands import Binner, BinComparator

binner = Binner(check_stability=True)
```

If you were already using the `riskbands` namespace, apply the class rename too:

```python
# before
from riskbands import RiskBandsBinner

# after
from riskbands import Binner
```

If you imported submodules directly, move them under `riskbands.*`.

Examples:

- `nasabinning.compare` -> `riskbands.compare`
- `nasabinning.reporting` -> `riskbands.reporting`
- `nasabinning.temporal_stability` -> `riskbands.temporal_stability`

## Why This Was Done

Keeping the longer class name after the package rename made the public API heavier than necessary. `riskbands.Binner` is shorter, cleaner, and still explicit enough in context.

This keeps the public surface structurally consistent:

- one project name
- one package namespace
- one main class name
- one distribution target

## What Did Not Change

- the focus on interpretable binning
- the emphasis on temporal stability in credit workflows
- the diagnostics, comparison, and audit-reporting philosophy

## Upgrade Checklist

1. Replace all `nasabinning` imports with `riskbands`.
2. Replace `NASABinner` with `Binner`.
3. Replace `RiskBandsBinner` with `Binner`.
4. Rebuild notebooks, scripts, and internal examples that used the old namespace or old class names.
5. Re-run your local tests or validation notebooks after the import update.
