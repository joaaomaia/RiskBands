"""
Auditable report generation for NASABinning objects.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Union

import pandas as pd

from .binning_engine import NASABinner

PathLike = Union[str, Path]


def _require_bin_summary(binner: NASABinner) -> pd.DataFrame:
    bin_summary = getattr(binner, "bin_summary", None)
    if bin_summary is None:
        raise RuntimeError("Binner ainda nao foi treinado.")
    return bin_summary


# ------------------------------------------------------------------ #
def save_binner_report(binner: NASABinner, path: PathLike) -> None:
    """
    Save bin table, summary metrics and optional temporal diagnostics.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.suffix.lower() == ".json":
        _save_json(binner, p)
    else:
        _save_excel(binner, p.with_suffix(".xlsx"))


def _save_excel(binner: NASABinner, path: Path) -> None:
    bin_summary = _require_bin_summary(binner)
    with pd.ExcelWriter(path) as writer:
        bin_summary.to_excel(writer, sheet_name="bin_table", index=False)
        meta = pd.DataFrame(
            {
                "metric": ["IV", "n_bins", "PSI_over_time"],
                "value": [
                    binner.iv_,
                    len(bin_summary),
                    bin_summary.attrs.get("psi_over_time"),
                ],
            }
        )
        meta.to_excel(writer, sheet_name="metrics", index=False)

        pivot = getattr(binner, "_pivot_", None)
        if pivot is not None:
            pivot.to_excel(writer, sheet_name="pivot_event_rate")

        diagnostics = getattr(binner, "_temporal_bin_diagnostics_", None)
        if diagnostics is not None:
            diagnostics.to_excel(writer, sheet_name="temporal_diag", index=False)

        summary = getattr(binner, "_temporal_variable_summary_", None)
        if summary is not None:
            summary.to_excel(writer, sheet_name="temporal_summary", index=False)


# ------------------------------------------------------------------ #
def _save_json(binner: NASABinner, path: Path) -> None:
    bin_summary = _require_bin_summary(binner)
    info = {
        "iv": binner.iv_,
        "iv_by_variable": getattr(binner, "iv_by_variable_", pd.Series(dtype=float)).to_dict(),
        "n_bins": len(bin_summary),
        "psi_over_time": bin_summary.attrs.get("psi_over_time"),
        "bin_table": bin_summary.to_dict(orient="records"),
    }
    pivot = getattr(binner, "_pivot_", None)
    if pivot is not None:
        info["pivot_event_rate"] = pivot.reset_index().to_dict(orient="records")
    diagnostics = getattr(binner, "_temporal_bin_diagnostics_", None)
    if diagnostics is not None:
        info["temporal_bin_diagnostics"] = diagnostics.to_dict(orient="records")
    summary = getattr(binner, "_temporal_variable_summary_", None)
    if summary is not None:
        info["temporal_variable_summary"] = summary.to_dict(orient="records")
    path.write_text(json.dumps(info, indent=2), encoding="utf-8")
