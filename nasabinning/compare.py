"""
Utilities to compare multiple NASABinner configurations.
"""

from __future__ import annotations

import inspect
from typing import Any

import pandas as pd

from .binning_engine import NASABinner
from .reporting import (
    build_candidate_profile_report,
    build_candidate_winner_report,
    build_variable_audit_report,
)
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


def _combine_alerts(values: pd.Series) -> str:
    alerts = []
    for value in values.fillna(""):
        for item in str(value).split(";"):
            item = item.strip()
            if item and item not in alerts:
                alerts.append(item)
    return ";".join(alerts)


class BinComparator:
    def __init__(self, configs: list[dict[str, Any]], time_col: str | None = None):
        self.configs = configs
        self.time_col = time_col
        self.results_ = []
        self._candidate_audit_report_ = pd.DataFrame()
        self._candidate_profile_summary_ = pd.DataFrame()
        self._winner_summary_ = pd.DataFrame()

    # -------------------------------------------------------------- #
    def fit_compare(self, X: pd.DataFrame, y: pd.Series):
        self.results_ = []
        audit_reports = []

        for raw_cfg in self.configs:
            name, cfg = _normalize_config(raw_cfg)
            binner = NASABinner(**cfg)
            binner.fit(X, y, time_col=self.time_col)

            psi = None
            if self.time_col:
                pivot = binner.stability_over_time(X, y, time_col=self.time_col)
                psi = psi_over_time(pivot)
                audit = build_variable_audit_report(
                    binner,
                    X,
                    y,
                    time_col=self.time_col,
                    dataset_name="comparison",
                    candidate_name=name,
                )
                audit_reports.append(audit)
            else:
                audit = pd.DataFrame()

            result = dict(
                name=name,
                strategy=binner.strategy,
                iv=binner.iv_,
                n_bins=len(binner.bin_summary),
                psi=psi,
                binner=binner,
            )

            if not audit.empty:
                result.update(
                    objective_score=float(audit["objective_score"].mean()),
                    temporal_score=float(audit["temporal_score"].mean()),
                    total_penalty=float(audit["objective_total_penalty"].mean()),
                    alert_flags=_combine_alerts(audit["alert_flags"]),
                )

            self.results_.append(result)

        if audit_reports:
            self._candidate_audit_report_ = pd.concat(audit_reports, ignore_index=True)
            self._candidate_profile_summary_ = build_candidate_profile_report(self._candidate_audit_report_)
            self._winner_summary_ = build_candidate_winner_report(self._candidate_profile_summary_)
        else:
            self._candidate_audit_report_ = pd.DataFrame()
            self._candidate_profile_summary_ = pd.DataFrame()
            self._winner_summary_ = pd.DataFrame()

        return self.fit_summary()

    # -------------------------------------------------------------- #
    def candidate_audit_report(self) -> pd.DataFrame:
        if self._candidate_audit_report_.empty:
            raise RuntimeError("Run fit_compare with time_col to build candidate audit reports.")
        return self._candidate_audit_report_.copy()

    # -------------------------------------------------------------- #
    def candidate_profile_summary(self) -> pd.DataFrame:
        if self._candidate_profile_summary_.empty:
            raise RuntimeError("Run fit_compare with time_col to build candidate profile summary.")
        return self._candidate_profile_summary_.copy()

    # -------------------------------------------------------------- #
    def winner_summary(self) -> pd.DataFrame:
        if self._winner_summary_.empty:
            raise RuntimeError("Run fit_compare with time_col to build winner summary.")
        return self._winner_summary_.copy()

    # -------------------------------------------------------------- #
    def to_excel(self, path: str):
        if not self.results_:
            raise RuntimeError("Run fit_compare first.")
        with pd.ExcelWriter(path) as writer:
            summary = self.fit_summary()
            summary.to_excel(writer, sheet_name="summary")

            if not self._candidate_audit_report_.empty:
                self._candidate_audit_report_.to_excel(
                    writer,
                    sheet_name="candidate_audit",
                    index=False,
                )
            if not self._candidate_profile_summary_.empty:
                self._candidate_profile_summary_.to_excel(
                    writer,
                    sheet_name="candidate_profiles",
                    index=False,
                )
            if not self._winner_summary_.empty:
                self._winner_summary_.to_excel(
                    writer,
                    sheet_name="winner_summary",
                    index=False,
                )

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
        summary = pd.DataFrame(self.results_).set_index("name")
        cols = ["strategy", "iv", "n_bins", "psi"]
        optional = [column for column in ["objective_score", "temporal_score", "total_penalty", "alert_flags"] if column in summary.columns]
        return summary[cols + optional]
