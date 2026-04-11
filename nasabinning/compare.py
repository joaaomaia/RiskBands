"""
Utilities to compare multiple NASABinner configurations.
"""

from __future__ import annotations

import inspect
from typing import Any

import pandas as pd

from .binning_engine import NASABinner
from .temporal_stability import psi_over_time


_BINNER_PARAMS = {
    name
    for name in inspect.signature(NASABinner.__init__).parameters
    if name != "self"
}


def _normalize_config(cfg: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    raw = dict(cfg)
    name = raw.pop("name", None) or raw.get("strategy", "binner")

    strategy_kwargs = dict(raw.pop("strategy_kwargs", {}) or {})
    extra_kwargs = {key: raw.pop(key) for key in list(raw) if key not in _BINNER_PARAMS}
    strategy_kwargs.update(extra_kwargs)
    if strategy_kwargs:
        raw["strategy_kwargs"] = strategy_kwargs

    return name, raw


class BinComparator:
    def __init__(self, configs: list[dict[str, Any]], time_col: str | None = None):
        self.configs = configs
        self.time_col = time_col
        self.results_ = []

    # -------------------------------------------------------------- #
    def fit_compare(self, X: pd.DataFrame, y: pd.Series):
        self.results_ = []
        for raw_cfg in self.configs:
            name, cfg = _normalize_config(raw_cfg)
            binner = NASABinner(**cfg)
            binner.fit(X, y, time_col=self.time_col)

            psi = None
            if self.time_col:
                pivot = binner.stability_over_time(X, y, time_col=self.time_col)
                psi = psi_over_time(pivot)

            self.results_.append(
                dict(
                    name=name,
                    strategy=binner.strategy,
                    iv=binner.iv_,
                    n_bins=len(binner.bin_summary),
                    psi=psi,
                    binner=binner,
                )
            )
        return pd.DataFrame(self.results_).set_index("name")

    # -------------------------------------------------------------- #
    def to_excel(self, path: str):
        if not self.results_:
            raise RuntimeError("Run fit_compare first.")
        with pd.ExcelWriter(path) as writer:
            summary = self.fit_summary()
            summary.to_excel(writer, sheet_name="summary")
            for res in self.results_:
                res["binner"].bin_summary.to_excel(
                    writer,
                    sheet_name=res["name"][:31],
                    index=False,
                )

    # -------------------------------------------------------------- #
    def fit_summary(self) -> pd.DataFrame:
        if not self.results_:
            raise RuntimeError("Run fit_compare first.")
        cols = ["strategy", "iv", "n_bins", "psi"]
        return pd.DataFrame(self.results_).set_index("name")[cols]
