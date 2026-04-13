import importlib
import re
from pathlib import Path

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


def test_package_version_matches_pyproject():
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    match = re.search(
        r'^version\s*=\s*"([^"]+)"\s*$',
        pyproject.read_text(encoding="utf-8"),
        flags=re.MULTILINE,
    )
    assert match is not None
    assert riskbands.__version__ == match.group(1)


def test_legacy_namespace_is_removed():
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("nasabinning")


def test_old_public_class_name_is_removed():
    with pytest.raises(ImportError):
        exec("from riskbands import RiskBandsBinner", {})
