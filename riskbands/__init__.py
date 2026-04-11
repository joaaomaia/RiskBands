"""Public package surface for RiskBands."""

from .binning_engine import Binner
from .compare import BinComparator
from .temporal_stability import ks_over_time, psi_over_time, temporal_separability_score

__all__ = [
    "Binner",
    "BinComparator",
    "ks_over_time",
    "psi_over_time",
    "temporal_separability_score",
]

__version__ = "1.0.0"


