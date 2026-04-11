import importlib

import pytest

import riskbands
from riskbands import (
    BinComparator,
    Binner,
    ks_over_time,
    psi_over_time,
    temporal_separability_score,
)
from riskbands.compare import BinComparator as ComparatorFromSubmodule
from riskbands.temporal_stability import ks_over_time as KsFromSubmodule


def test_public_api_exports_are_importable():
    assert Binner is not None
    assert BinComparator is not None
    assert ComparatorFromSubmodule is BinComparator
    assert ks_over_time is KsFromSubmodule
    assert psi_over_time is not None
    assert temporal_separability_score is not None


def test_package_version_matches_breaking_release():
    assert riskbands.__version__ == "1.0.0"


def test_legacy_namespace_is_removed():
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("nasabinning")


def test_old_public_class_name_is_removed():
    with pytest.raises(ImportError):
        exec("from riskbands import RiskBandsBinner", {})

