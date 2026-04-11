import nasabinning
import riskbands
from riskbands import (
    BinComparator,
    NASABinner,
    RiskBandsBinner,
    ks_over_time,
    psi_over_time,
    temporal_separability_score,
)
from riskbands.compare import BinComparator as ComparatorFromSubmodule


def test_public_api_exports_are_importable():
    assert RiskBandsBinner is not None
    assert NASABinner is not None
    assert BinComparator is not None
    assert ComparatorFromSubmodule is BinComparator
    assert ks_over_time is not None
    assert psi_over_time is not None
    assert temporal_separability_score is not None


def test_package_version_matches_sprint_checkpoint():
    assert riskbands.__version__ == "0.6.0b0"
    assert nasabinning.__version__ == "0.6.0b0"


def test_legacy_namespace_remains_compatible():
    assert nasabinning.NASABinner is NASABinner
    assert nasabinning.RiskBandsBinner is RiskBandsBinner
