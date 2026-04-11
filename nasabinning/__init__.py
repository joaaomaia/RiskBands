"""Compatibility package surface for the legacy ``nasabinning`` namespace."""

from .binning_engine import NASABinner
from .compare import BinComparator
from .temporal_stability import ks_over_time, psi_over_time, temporal_separability_score

RiskBandsBinner = NASABinner

__all__ = [
    "RiskBandsBinner",
    "NASABinner",
    "BinComparator",
    "ks_over_time",
    "psi_over_time",
    "temporal_separability_score",
]
__version__ = "0.6.0b0"
