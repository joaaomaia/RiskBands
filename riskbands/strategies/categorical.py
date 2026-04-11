from __future__ import annotations
import pandas as pd
from optbinning import OptimalBinning
from category_encoders.ordinal import OrdinalEncoder


class CategoricalBinning:
    """
    Rare-merge + OptimalBinning(dtype='categorical').

    Se o solver falhar (ou resultar <2 bins), recorre a encoder ordinal.
    """

    def __init__(
        self,
        rare_threshold: float = 0.01,
        max_bins: int = 6,
        min_bin_size: float = 0.05,   # repassado ao OptimalBinning
    ):
        self.rare_threshold = rare_threshold
        self.max_bins = max_bins
        self.min_bin_size = min_bin_size
        self._encoder = None          # (obj, "woe"|"ordinal")
        self.bin_summary_ = None

    # ------------------------------------------------------------------
    def fit(self, X: pd.DataFrame, y: pd.Series, **kwargs):
        assert X.shape[1] == 1, "Passe apenas uma coluna por vez"
        col = X.columns[0]
        s = X[col].astype("category")

        # ---------- Rare-merge ----------------------------------------
        freq = s.value_counts(normalize=True)
        rare = freq[freq < self.rare_threshold].index
        s = s.replace(rare, "_RARE_").astype("category")

        # ---------- Tenta OptimalBinning ------------------------------
        ob = OptimalBinning(
            name=col,
            dtype="categorical",
            solver="cp",
            max_n_bins=self.max_bins,
            min_bin_size=self.min_bin_size,
            prebin_cat=True,
        )

        try:
            ob.fit(s.to_numpy(), y.to_numpy())
            codes = ob.transform(s.to_numpy(), metric="bins")
            if len(pd.unique(codes)) < 2:
                raise ValueError("Resultou em menos de 2 bins")
            self._encoder = (ob, "woe")
        except Exception:
            # ---------- Fallback ordinal ------------------------------
            enc = OrdinalEncoder(cols=[col], handle_unknown="value", handle_missing="value")
            codes = enc.fit_transform(s)[col]
            self._encoder = (enc, "ordinal")

        # ---------- bin_summary_ --------------------------------------
        df = pd.DataFrame({col: codes, "target": y})
        summary = (
            df.groupby(col)["target"]
              .agg(["count", "sum"])
              .rename(columns={"sum": "event"})
              .assign(non_event=lambda d: d["count"] - d["event"],
                      event_rate=lambda d: d["event"] / d["count"])
              .reset_index()
              .rename(columns={col: "bin"})
        )
        summary.insert(0, "variable", col)
        self.bin_summary_ = summary
        return self

    # ------------------------------------------------------------------
    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        col = X.columns[0]
        if self._encoder[1] == "woe":
            codes = self._encoder[0].transform(
                X[col].astype("category").to_numpy(), metric="bins"
            )
            return pd.DataFrame({col: codes})
        else:
            return self._encoder[0].transform(X[[col]])

