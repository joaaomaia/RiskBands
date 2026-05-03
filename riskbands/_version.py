"""Version helpers shared across the RiskBands package."""

from __future__ import annotations

import re
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path


def infer_local_version() -> str:
    pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
    try:
        content = pyproject.read_text(encoding="utf-8")
    except OSError:  # pragma: no cover - best effort fallback
        return "0.0.0"

    match = re.search(r'^version\s*=\s*"([^"]+)"\s*$', content, flags=re.MULTILINE)
    return match.group(1) if match else "0.0.0"


def resolve_version() -> str:
    local_version = infer_local_version()
    package_dir = Path(__file__).resolve().parent
    try:
        dist = distribution("riskbands")
        if Path(dist.locate_file("riskbands")).resolve() == package_dir:
            return dist.version if local_version == "0.0.0" else local_version
    except PackageNotFoundError:
        return local_version
    except Exception:  # pragma: no cover - metadata lookup is best effort
        return local_version

    return local_version
