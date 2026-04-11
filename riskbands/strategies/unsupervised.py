"""
Unsupervised numeric binning strategies built on top of KBinsDiscretizer.
"""

from __future__ import annotations

import pandas as pd
from sklearn.preprocessing import KBinsDiscretizer


class UnsupervisedBinning:
    def __init__(
        self,
        method: str = "quantile",
        n_bins: int = 10,
    ):
        if method not in {"uniform", "quantile", "kmeans"}:
            raise ValueError("method must be uniform, quantile or kmeans")
        self.method = method
        self.n_bins = n_bins
        self._kbd = None
        self.bin_summary_ = None

    # -------------------------------------------------------------- #
    def fit(self, X: pd.DataFrame, y=None, **kwargs):
        self._kbd = KBinsDiscretizer(
            n_bins=self.n_bins,
            encode="ordinal",
            strategy=self.method,
        )
        self._kbd.fit(X)

        if y is not None:
            Xt = self.transform(X)
            summaries = []
            for col in Xt.columns:
                df = pd.DataFrame({col: Xt[col], "target": y}, index=X.index)
                summary = (
                    df.groupby(col)["target"]
                    .agg(["count", "sum"])
                    .rename(columns={"sum": "event"})
                    .assign(
                        non_event=lambda d: d["count"] - d["event"],
                        event_rate=lambda d: d["event"] / d["count"],
                    )
                    .reset_index()
                    .rename(columns={col: "bin"})
                )
                summary.insert(0, "variable", col)
                summaries.append(summary)

            self.bin_summary_ = pd.concat(summaries, ignore_index=True)

        return self

    # -------------------------------------------------------------- #
    def transform(self, X: pd.DataFrame, return_woe: bool = False):
        if return_woe:
            raise NotImplementedError("WoE requer target supervisionado.")
        Xt = self._kbd.transform(X)
        return pd.DataFrame(Xt, columns=X.columns, index=X.index)


