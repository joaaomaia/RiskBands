import nasabinning
from nasabinning import (
    BinComparator,
    NASABinner,
    ks_over_time,
    psi_over_time,
    temporal_separability_score,
)


def test_public_api_exports_are_importable():
    assert NASABinner is not None
    assert BinComparator is not None
    assert ks_over_time is not None
    assert psi_over_time is not None
    assert temporal_separability_score is not None


def test_package_version_matches_sprint_checkpoint():
    assert nasabinning.__version__ == "0.6.0b0"
