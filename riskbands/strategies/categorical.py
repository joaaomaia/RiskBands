from __future__ import annotations

import inspect

import pandas as pd
from optbinning import OptimalBinning


class CategoricalBinning:
    """
    Supervised categorical binning with deterministic rare/missing handling.

    The class attempts to use ``OptimalBinning(dtype="categorical")`` when the
    installed version proves safe for train, rare, missing and unknown values.
    Otherwise it falls back to a local event-rate based encoder.
    """

    def __init__(
        self,
        rare_threshold: float = 0.01,
        max_bins: int = 6,
        min_bin_size: float = 0.05,
    ):
        self.rare_threshold = rare_threshold
        self.max_bins = max_bins
        self.min_bin_size = min_bin_size
        self.missing_token_ = "_MISSING_"
        self.rare_token_ = "_RARE_"
        self.unknown_token_ = "_UNKNOWN_"
        self._encoder = None
        self._fallback_reason_ = None
        self.bin_summary_ = None

    # ------------------------------------------------------------------
    def _prepare_series(self, X: pd.DataFrame, *, fit: bool) -> pd.Series:
        if not isinstance(X, pd.DataFrame):
            raise TypeError("`X` must be a pandas DataFrame.")
        if X.shape[1] != 1:
            raise ValueError("Passe apenas uma coluna por vez")

        col = X.columns[0]
        values = X[col].copy().astype("object")
        missing = values.isna()
        normalized = values.map(lambda value: str(value))
        normalized.loc[missing] = self.missing_token_
        normalized = normalized.rename(col)

        if fit:
            freq = normalized.value_counts(normalize=True, sort=False)
            if self.rare_threshold and self.rare_threshold > 0:
                rare = freq[
                    (freq < self.rare_threshold)
                    & (~freq.index.isin([self.missing_token_]))
                ].index
            else:
                rare = pd.Index([])

            self.feature_name_ = col
            self.rare_categories_ = sorted(map(str, rare))
            self._rare_categories_set_ = set(self.rare_categories_)

            prepared = normalized.mask(normalized.isin(self._rare_categories_set_), self.rare_token_)
            self.known_categories_ = sorted(prepared.unique().tolist())
            self._known_categories_set_ = set(self.known_categories_)
            return prepared.rename(col)

        if not hasattr(self, "_known_categories_set_"):
            raise RuntimeError("CategoricalBinning has not been fitted yet.")

        prepared = normalized.mask(normalized.isin(self._rare_categories_set_), self.rare_token_)
        known = prepared.isin(self._known_categories_set_)
        prepared = prepared.where(known, self.unknown_token_)
        return prepared.rename(getattr(self, "feature_name_", col))

    # ------------------------------------------------------------------
    @staticmethod
    def _coerce_target(y: pd.Series, index: pd.Index) -> pd.Series:
        if len(y) != len(index):
            raise ValueError(
                f"`y` must have the same length as `X`. Expected {len(index)} values, got {len(y)}."
            )
        if isinstance(y, pd.Series):
            target = pd.Series(y.to_numpy(), index=index, name=y.name or "target")
        else:
            target = pd.Series(y, index=index, name="target")
        return pd.to_numeric(target, errors="raise")

    # ------------------------------------------------------------------
    def _build_summary_from_codes(
        self,
        codes: pd.Series,
        y: pd.Series,
    ) -> pd.DataFrame:
        col = self.feature_name_
        df = pd.DataFrame({"bin": codes.to_numpy(), "target": y.to_numpy()}, index=codes.index)
        summary = (
            df.groupby("bin", sort=True, dropna=False)["target"]
            .agg(count="count", event="sum")
            .reset_index()
        )
        summary["non_event"] = summary["count"] - summary["event"]
        summary["event_rate"] = summary["event"] / summary["count"]
        summary.insert(0, "variable", col)
        return summary[["variable", "bin", "count", "event", "non_event", "event_rate"]]

    # ------------------------------------------------------------------
    def _select_default_bin(self, summary: pd.DataFrame):
        ordered = summary.sort_values(
            by=["count", "event_rate", "bin"],
            ascending=[False, True, True],
            kind="mergesort",
        )
        return ordered["bin"].iloc[0]

    # ------------------------------------------------------------------
    def _expand_rare_category_mapping(self, mapping: dict) -> dict:
        if self.rare_token_ not in mapping:
            return mapping
        rare_bin = mapping[self.rare_token_]
        for category in self.rare_categories_:
            mapping.setdefault(category, rare_bin)
        return mapping

    # ------------------------------------------------------------------
    def _fit_manual(self, prepared: pd.Series, y: pd.Series, reason: str):
        stats = (
            pd.DataFrame({"category": prepared, "target": y})
            .groupby("category", sort=False, dropna=False)["target"]
            .agg(count="count", event="sum")
            .reset_index()
        )
        if stats.empty:
            raise ValueError("Cannot fit CategoricalBinning with an empty column.")

        stats["non_event"] = stats["count"] - stats["event"]
        stats["event_rate"] = stats["event"] / stats["count"]
        stats = stats.sort_values(
            by=["event_rate", "category"],
            ascending=[True, True],
            kind="mergesort",
        ).reset_index(drop=True)

        max_bins = int(self.max_bins) if self.max_bins else len(stats)
        n_bins = max(1, min(max_bins, len(stats)))
        stats["bin"] = (stats.index.to_series() * n_bins // len(stats)).astype(int)

        mapping = dict(zip(stats["category"], stats["bin"]))
        codes = prepared.map(mapping).rename(self.feature_name_)
        summary = self._build_summary_from_codes(codes, y)
        default_bin = self._select_default_bin(summary)

        mapping = self._expand_rare_category_mapping(mapping)
        mapping[self.unknown_token_] = default_bin
        if self.missing_token_ not in mapping:
            mapping[self.missing_token_] = default_bin

        self.category_mapping_ = mapping
        self.default_bin_ = default_bin
        self._encoder = (mapping, "manual")
        self._fallback_reason_ = reason
        self.bin_summary_ = summary
        return self

    # ------------------------------------------------------------------
    def _optimal_binning_kwargs(self) -> dict:
        kwargs = {
            "name": self.feature_name_,
            "dtype": "categorical",
            "solver": "cp",
            "max_n_bins": self.max_bins,
            "min_bin_size": self.min_bin_size,
        }
        signature = inspect.signature(OptimalBinning.__init__)
        return {key: value for key, value in kwargs.items() if key in signature.parameters}

    # ------------------------------------------------------------------
    def _fit_optimal_binning(self, prepared: pd.Series, y: pd.Series) -> tuple[pd.Series, OptimalBinning]:
        ob = OptimalBinning(**self._optimal_binning_kwargs())
        ob.fit(prepared.to_numpy(dtype=object), y.to_numpy())

        train_codes = pd.Series(
            ob.transform(prepared.to_numpy(dtype=object), metric="bins"),
            index=prepared.index,
            name=self.feature_name_,
        )
        if train_codes.nunique(dropna=False) < 2:
            raise ValueError("OptimalBinning categorical produced fewer than 2 bins.")

        probe_values = [prepared.iloc[0], self.missing_token_, self.unknown_token_]
        if self.rare_token_ in self.known_categories_:
            probe_values.append(self.rare_token_)
        probe_codes = pd.Series(
            ob.transform(pd.Series(probe_values).to_numpy(dtype=object), metric="bins")
        )
        known_bins = set(train_codes.astype(str))
        if not probe_codes.astype(str).isin(known_bins).all():
            raise ValueError("OptimalBinning categorical created out-of-summary bins for probe values.")

        categories = pd.Series(self.known_categories_, name=self.feature_name_)
        category_codes = ob.transform(categories.to_numpy(dtype=object), metric="bins")
        self.category_mapping_ = dict(zip(categories.astype(str), category_codes))
        self.category_mapping_ = self._expand_rare_category_mapping(self.category_mapping_)
        self.default_bin_ = probe_codes.iloc[2]
        self.category_mapping_[self.unknown_token_] = self.default_bin_
        if self.missing_token_ not in self.category_mapping_:
            self.category_mapping_[self.missing_token_] = self.default_bin_
        return train_codes, ob

    # ------------------------------------------------------------------
    def fit(self, X: pd.DataFrame, y: pd.Series, **kwargs):
        prepared = self._prepare_series(X, fit=True)
        target = self._coerce_target(y, prepared.index)

        try:
            codes, ob = self._fit_optimal_binning(prepared, target)
            self._encoder = (ob, "optimal")
            self._fallback_reason_ = None
            self.bin_summary_ = self._build_summary_from_codes(codes, target)
        except Exception as exc:
            self._fit_manual(prepared, target, reason=str(exc))
        return self

    # ------------------------------------------------------------------
    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        if self._encoder is None:
            raise RuntimeError("CategoricalBinning has not been fitted yet.")

        prepared = self._prepare_series(X, fit=False)
        encoder, enc_type = self._encoder

        if enc_type == "optimal":
            values = encoder.transform(prepared.to_numpy(dtype=object), metric="bins")
            codes = pd.Series(values, index=prepared.index, name=self.feature_name_)
            known_bins = set(self.bin_summary_["bin"].astype(str))
            codes = codes.where(codes.astype(str).isin(known_bins), self.default_bin_)
        elif enc_type == "manual":
            codes = prepared.map(encoder).fillna(self.default_bin_).rename(self.feature_name_)
        else:  # pragma: no cover - defensive guard for old serialized objects.
            raise RuntimeError("Tipo de encoder desconhecido.")

        return pd.DataFrame({self.feature_name_: codes}, index=prepared.index)
