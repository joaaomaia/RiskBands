"""Public package surface for RiskBands."""

from __future__ import annotations

import re
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path

from .binning_engine import Binner
from .compare import BinComparator
from .temporal_stability import ks_over_time, psi_over_time, temporal_separability_score


def _infer_local_version() -> str:
    pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
    try:
        content = pyproject.read_text(encoding="utf-8")
    except OSError:  # pragma: no cover - best effort fallback
        return "0.0.0"

    match = re.search(r'^version\s*=\s*"([^"]+)"\s*$', content, flags=re.MULTILINE)
    return match.group(1) if match else "0.0.0"


def _resolve_version() -> str:
    local_version = _infer_local_version()
    package_dir = Path(__file__).resolve().parent
    try:
        dist = distribution("riskbands")
        if Path(dist.locate_file("riskbands")).resolve() == package_dir:
            return local_version or dist.version
    except PackageNotFoundError:
        pass
    except Exception:  # pragma: no cover - metadata lookup is best effort
        pass

    return local_version


__all__ = [
    "Binner",
    "BinComparator",
    "ks_over_time",
    "psi_over_time",
    "temporal_separability_score",
]

__version__ = _resolve_version()
