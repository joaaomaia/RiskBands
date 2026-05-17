import importlib
import re
from pathlib import Path

import pytest

import riskbands
from riskbands import (
    BinComparator,
    Binner,
    RiskBands,
    ks_over_time,
    psi_over_time,
    temporal_separability_score,
)
from riskbands.compare import BinComparator as ComparatorFromSubmodule
from riskbands.temporal_stability import ks_over_time as KsFromSubmodule


def test_public_api_exports_are_importable():
    assert RiskBands is not None
    assert Binner is not None
    assert RiskBands is Binner
    assert BinComparator is not None
    assert ComparatorFromSubmodule is BinComparator
    assert ks_over_time is KsFromSubmodule
    assert psi_over_time is not None
    assert temporal_separability_score is not None


def test_riskbands_preferred_import_styles_construct_equivalent_objects():
    from riskbands import RiskBands as rb

    preferred = RiskBands()
    alias_style = rb()
    package_style = riskbands.RiskBands()
    compatible = Binner()

    assert isinstance(preferred, Binner)
    assert isinstance(alias_style, Binner)
    assert isinstance(package_style, Binner)
    assert type(preferred) is type(compatible)
    assert "RiskBands" in riskbands.__all__
    assert "Binner" in riskbands.__all__


def test_no_capitalized_riskbands_module_is_introduced():
    root = Path(__file__).resolve().parents[1]
    child_names = {path.name for path in root.iterdir()}
    assert "RiskBands" not in child_names
    assert "RiskBands.py" not in child_names


def test_package_version_matches_pyproject():
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    match = re.search(
        r'^version\s*=\s*"([^"]+)"\s*$',
        pyproject.read_text(encoding="utf-8"),
        flags=re.MULTILINE,
    )
    assert match is not None
    assert riskbands.__version__ == match.group(1)


def test_resolve_version_uses_distribution_version_when_local_pyproject_is_missing(monkeypatch):
    package_dir = Path(riskbands.__file__).resolve().parent

    class FakeDistribution:
        version = "9.9.9"

        def locate_file(self, name: str) -> Path:
            assert name == "riskbands"
            return package_dir

    monkeypatch.setattr(riskbands, "_infer_local_version", lambda: "0.0.0")
    monkeypatch.setattr(riskbands, "distribution", lambda _: FakeDistribution())

    assert riskbands._resolve_version() == "9.9.9"


def test_legacy_namespace_is_removed():
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("nasabinning")


def test_old_public_class_name_is_removed():
    with pytest.raises(ImportError):
        exec("from riskbands import RiskBandsBinner", {})


def test_old_score_strategy_name_is_absent_from_public_materials():
    root = Path(__file__).resolve().parents[1]
    old_name = "generalization" + "_v1"
    paths = [
        root / "README.md",
        root / "docs" / "api_reference.md",
        *sorted((root / "docs-site" / "src" / "content" / "docs" / "technical").rglob("*.md")),
        *sorted((root / "examples").rglob("*.py")),
        *sorted((root / "examples").rglob("*.ipynb")),
        *sorted((root / "riskbands").rglob("*.py")),
    ]

    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert old_name not in text, f"Unexpected legacy score name in {path}"


def test_old_score_strategy_name_is_rejected():
    old_name = "generalization" + "_v1"

    with pytest.raises(ValueError, match="Unsupported score strategy"):
        Binner(score_strategy=old_name)
