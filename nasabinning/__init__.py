"""Public package surface for NASABinning."""

from .binning_engine import NASABinner
from .compare import BinComparator
from .temporal_stability import ks_over_time, psi_over_time, temporal_separability_score

__all__ = [
    "NASABinner",
    "BinComparator",
    "ks_over_time",
    "psi_over_time",
    "temporal_separability_score",
]
__version__ = "0.6.0b0"
