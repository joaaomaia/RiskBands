"""
Wrapper de OptimalBinning â€” apenas binagem supervisionada.
"""
import pandas as pd
from optbinning import OptimalBinning


class SupervisedBinning:
    """Aplica OptimalBinning em **cada** coluna numÃ©rica do DataFrame."""

    def __init__(self, max_bins: int = 10, min_bin_size: float = 0.05):
        self.max_bins = max_bins
        self.min_bin_size = min_bin_size
        self.models_ = {}          # col -> OptimalBinning
        self.bin_summary_ = None

    # -------------------------------------------------------------- #
    def fit(self, X: pd.DataFrame, y, monotonic_trend=None):
        summaries = []
        for col in X.columns:
            ob = OptimalBinning(
                name=col,
                solver="cp",
                monotonic_trend=monotonic_trend,
                max_n_bins=self.max_bins,
                min_bin_size=self.min_bin_size,
            )
            ob.fit(X[col].values, y.values)
            self.models_[col] = ob
            tbl = ob.binning_table.build()
            tbl["variable"] = col
            summaries.append(tbl)

        self.bin_summary_ = pd.concat(summaries, ignore_index=True)
        return self

    # -------------------------------------------------------------- #
    def transform(self, X: pd.DataFrame, return_woe=False):
        dfs = []
        for col, ob in self.models_.items():
            if return_woe:
                tr = ob.transform(X[col].values, metric="woe")
            else:
                tr = ob.transform(X[col].values, metric="bins")
            dfs.append(pd.DataFrame({col: tr}, index=X.index))
        return pd.concat(dfs, axis=1)


