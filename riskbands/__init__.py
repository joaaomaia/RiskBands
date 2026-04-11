"""Public package surface for RiskBands.

RiskBands is the new project identity for the library formerly called
``NASABinning``. The legacy ``nasabinning`` package remains available as a
compatibility namespace during the migration window.
"""

from __future__ import annotations

from importlib import import_module
import sys

from nasabinning import (
    BinComparator,
    NASABinner,
    RiskBandsBinner,
    ks_over_time,
    psi_over_time,
    temporal_separability_score,
)
from nasabinning import __version__

__all__ = [
    "RiskBandsBinner",
    "NASABinner",
    "BinComparator",
    "ks_over_time",
    "psi_over_time",
    "temporal_separability_score",
]

_ALIASED_SUBMODULES = [
    "binning_engine",
    "compare",
    "metrics",
    "optuna_optimizer",
    "refinement",
    "reporting",
    "temporal_diagnostics",
    "temporal_stability",
    "validators",
    "visualizations",
    "strategies",
    "utils",
]

for _submodule in _ALIASED_SUBMODULES:
    sys.modules.setdefault(
        f"{__name__}.{_submodule}",
        import_module(f"nasabinning.{_submodule}"),
    )
