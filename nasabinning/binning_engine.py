"""
Core orchestration for NASABinning.

This module coordinates the binning strategy, post-processing, and temporal
stability utilities exposed by ``NASABinner``.
"""

from __future__ import annotations

import inspect

import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin

from .metrics import iv
from .refinement import refine_bins
from .strategies import get_strategy
from .utils.dtypes import search_dtypes


class NASABinner(BaseEstimator, TransformerMixin):
    def __init__(
        self,
        strategy: str = "supervised",
        max_bins: int = 6,
        min_event_rate_diff: float = 0.02,
        monotonic: str | None = None,
        check_stability: bool = False,
        use_optuna: bool = False,
        time_col: str | None = None,
        force_categorical: list[str] | None = None,
        force_numeric: list[str] | None = None,
        strategy_kwargs: dict | None = None,
    ):
        self.strategy = strategy
        self.max_bins = max_bins
        self.min_event_rate_diff = min_event_rate_diff
        self.monotonic = monotonic
        self.check_stability = check_stability
        self.use_optuna = use_optuna
        self.time_col = time_col
        self.force_categorical = force_categorical or []
        self.force_numeric = force_numeric or []

        strategy_kwargs = strategy_kwargs or {}
        if "strategy_kwargs" in strategy_kwargs:
            nested = strategy_kwargs.pop("strategy_kwargs")
            for key, value in nested.items():
                strategy_kwargs.setdefault(key, value)
        self.strategy_kwargs = strategy_kwargs

        self._fitted_strategy = None
        self.bin_summary = None

    # ------------------------------------------------------------------
    def _numeric_strategy_kwargs(self) -> dict:
        kwargs = dict(self.strategy_kwargs)
        if self.strategy == "supervised":
            kwargs.setdefault("max_bins", self.max_bins)
        elif self.strategy == "unsupervised":
            kwargs.setdefault("n_bins", self.max_bins)
        else:
            raise ValueError(
                f"Numeric strategy '{self.strategy}' is not supported. "
                "Use 'supervised' or 'unsupervised'."
            )
        return kwargs

    # ------------------------------------------------------------------
    def _compute_iv_metrics(self) -> None:
        iv_by_variable = {
            variable: iv(group)
            for variable, group in self.bin_summary.groupby("variable", sort=False)
        }
        self.iv_by_variable_ = pd.Series(iv_by_variable, name="iv")
        self.iv_ = float(self.iv_by_variable_.sum())

    # ------------------------------------------------------------------
    @property
    def bin_summary_(self) -> pd.DataFrame:
        return self.bin_summary

    # ------------------------------------------------------------------
    @property
    def _bin_summary_(self) -> pd.DataFrame:
        return self.bin_summary

    # ------------------------------------------------------------------
    def fit(self, X: pd.DataFrame, y: pd.Series, *, time_col: str | None = None):
        """Fit the binner. When ``use_optuna=True`` optimization is done per feature."""
        assert isinstance(X, pd.DataFrame), "X deve ser um DataFrame"
        assert isinstance(y, pd.Series), "y deve ser uma Series"

        time_col = time_col or self.time_col
        self.time_col = time_col
        X_features = X.drop(columns=[time_col], errors="ignore") if time_col else X.copy()

        num_cols, cat_cols = search_dtypes(
            pd.concat([X_features, y.rename("target")], axis=1),
            target_col="target",
            limite_categorico=50,
            force_categorical=self.force_categorical,
            verbose=False,
        )

        self.numeric_cols_ = num_cols
        self.cat_cols_ = cat_cols
        self.time_cols_ = [time_col] if time_col and time_col in X.columns else []
        self.ignored_cols_ = [c for c in X_features.columns if c not in num_cols + cat_cols]

        if self.use_optuna:
            if self.strategy != "supervised":
                raise ValueError("Optuna is currently supported only for strategy='supervised'.")

            from .optuna_optimizer import optimize_bins

            optuna_kwargs = dict(self.strategy_kwargs)
            n_trials = optuna_kwargs.pop("n_trials", 20)
            objective_kwargs = optuna_kwargs.pop("objective_kwargs", None)
            base_kwargs = dict(
                strategy=self.strategy,
                min_event_rate_diff=self.min_event_rate_diff,
                monotonic=self.monotonic,
                check_stability=self.check_stability,
            )
            self._per_feature_binners = {}
            self.best_params_ = {}
            self.objective_summaries_ = {}

            for col in num_cols + cat_cols:
                time_values = X[time_col] if time_col else None
                best, fitted_binner = optimize_bins(
                    X_features[[col]],
                    y,
                    time_col=time_col,
                    time_values=time_values,
                    n_trials=n_trials,
                    objective_kwargs=objective_kwargs,
                    **base_kwargs,
                )
                self._per_feature_binners[col] = fitted_binner
                self.best_params_[col] = best
                self.objective_summaries_[col] = getattr(fitted_binner, "objective_summary_", None)

            self.bin_summary = pd.concat(
                [binner.bin_summary for binner in self._per_feature_binners.values()],
                ignore_index=True,
            )
            self._compute_iv_metrics()
            return self

        self._per_feature_binners = {}
        summaries = []

        for col in num_cols:
            strat = get_strategy(self.strategy, **self._numeric_strategy_kwargs())
            strat.fit(X_features[[col]], y, monotonic_trend=self.monotonic)

            summary = refine_bins(
                strat.bin_summary_,
                min_er_delta=self.min_event_rate_diff,
                trend=self.monotonic,
                time_col=time_col,
                check_stability=self.check_stability,
            )
            summary = summary[
                (summary["count"] > 0)
                & (~summary["bin"].astype(str).str.lower().isin(["total", "special", "missing"]))
                & (summary["bin"] != summary["variable"])
                & (summary["bin"] != "")
            ].reset_index(drop=True)

            self._per_feature_binners[col] = strat
            summaries.append(summary)

        for col in cat_cols:
            from .strategies.categorical import CategoricalBinning

            strat = CategoricalBinning(max_bins=self.max_bins)
            strat.fit(X_features[[col]], y)

            summary = refine_bins(
                strat.bin_summary_,
                min_er_delta=self.min_event_rate_diff,
                trend=None,
                time_col=None,
                check_stability=False,
            )
            summary = summary[
                (summary["count"] > 0)
                & (~summary["bin"].astype(str).str.lower().isin(["total", "special", "missing"]))
                & (summary["bin"] != summary["variable"])
                & (summary["bin"] != "")
            ].reset_index(drop=True)
            summary = summary.sort_values("event_rate", ascending=False).reset_index(drop=True)

            self._per_feature_binners[col] = strat
            summaries.append(summary)

        self.bin_summary = pd.concat(summaries, ignore_index=True)
        self._compute_iv_metrics()
        return self

    # ------------------------------------------------------------------
    def transform(self, X: pd.DataFrame, *, return_woe: bool = False):
        out = {}
        for col, binner in self._per_feature_binners.items():
            sig = inspect.signature(binner.transform)
            kwargs = {"return_woe": return_woe} if "return_woe" in sig.parameters else {}
            out[col] = binner.transform(X[[col]], **kwargs)[col]
        return pd.DataFrame(out, index=X.index)

    # ------------------------------------------------------------------
    def describe_schema(self) -> pd.DataFrame:
        """Return a compact schema summary for the fitted dataset."""
        records = []
        for col in self.numeric_cols_:
            records.append({"col": col, "tipo": "numeric"})
        for col in self.cat_cols_:
            records.append({"col": col, "tipo": "categorical"})
        for col in getattr(self, "time_cols_", []):
            records.append({"col": col, "tipo": "time"})
        for col in getattr(self, "ignored_cols_", []):
            records.append({"col": col, "tipo": "ignored"})
        return pd.DataFrame(records)

    # ------------------------------------------------------------------
    def fit_transform(self, X: pd.DataFrame, y: pd.Series, **fit_params):
        return self.fit(X, y, **fit_params).transform(X)

    # ------------------------------------------------------------------
    def get_bin_mapping(self, column: str) -> pd.DataFrame:
        """
        Return a category -> bin mapping for a fitted categorical feature.
        """
        if hasattr(self, "_per_feature_binners") and column in self._per_feature_binners:
            binner_col = self._per_feature_binners[column]
        else:
            if self._fitted_strategy is None:
                raise RuntimeError("O binner ainda nao foi treinado.")
            binner_col = self._fitted_strategy

        if not hasattr(binner_col, "_encoder"):
            raise ValueError(f"A coluna '{column}' nao passou por CategoricalBinning.")
        encoder, enc_type = binner_col._encoder

        if enc_type == "woe":
            mapping = encoder.splits["mapping"]
        elif enc_type == "ordinal":
            mapping = encoder.mapping[0]["mapping"]
        else:
            raise RuntimeError("Tipo de encoder desconhecido.")

        return (
            pd.Series(mapping, name="bin")
            .reset_index()
            .rename(columns={"index": "categoria"})
            .sort_values("bin")
            .reset_index(drop=True)
        )

    # ------------------------------------------------------------------
    def stability_over_time(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        *,
        time_col: str,
        fill_value: float | None = None,
    ) -> pd.DataFrame:
        """
        Compute event-rate by bin across time periods.

        Returns a pivot table indexed by ``(variable, bin)`` and with time
        periods as columns.
        """
        if time_col not in X.columns:
            raise KeyError(
                f"time_col='{time_col}' nao esta em X. "
                "Inclua a coluna de safra no DataFrame passado."
            )
        if not hasattr(self, "_per_feature_binners"):
            raise RuntimeError("Binner ainda nao foi treinado. Chame .fit() antes.")

        parts = []
        for col, binner in self._per_feature_binners.items():
            if col not in X.columns:
                raise KeyError(f"Feature '{col}' nao esta presente em X.")

            sig = inspect.signature(binner.transform)
            kwargs = {"return_woe": False} if "return_woe" in sig.parameters else {}
            transformed = binner.transform(X[[col]], **kwargs)
            series = transformed if isinstance(transformed, pd.Series) else transformed[col]
            parts.append(series.rename(col))

        X_bins = pd.concat(parts, axis=1)

        df_aux = pd.concat([X_bins, y.rename("target"), X[time_col]], axis=1)

        out = []
        for var in X_bins.columns:
            grp = (
                df_aux.groupby([time_col, var])["target"]
                .agg(["sum", "count"])
                .reset_index()
                .rename(columns={"sum": "event", "count": "total", var: "bin"})
            )
            grp["event_rate"] = grp["event"] / grp["total"]
            grp["variable"] = var
            out.append(grp)

        df_rate = pd.concat(out, ignore_index=True)

        pivot_kwargs = {
            "index": ["variable", "bin"],
            "columns": time_col,
            "values": "event_rate",
        }
        if fill_value is not None:
            pivot_kwargs["fill_value"] = fill_value

        pivot = df_rate.pivot_table(**pivot_kwargs).sort_index(axis=1).sort_index()
        self._pivot_ = pivot
        self._stability_table_ = df_rate
        return pivot

    # ------------------------------------------------------------------
    def _bin_code_to_label(self, var: str) -> dict:
        """
        Return a mapping {bin_code -> interval label} for the given feature.
        """
        bs = self.bin_summary.loc[self.bin_summary["variable"] == var].copy()

        for candidate in ("bin_code", "bin_code_float", "bin_code_int"):
            if candidate in bs.columns:
                key_col = candidate
                break
        else:
            bs = bs.reset_index(drop=True)
            bs["__pos__"] = bs.index.astype(float)
            key_col = "__pos__"

        return {bs[key_col].iloc[i]: str(bs["bin"].iloc[i]) for i in range(len(bs))}

    # ------------------------------------------------------------------
    def plot_event_rate_stability(self, pivot: pd.DataFrame | None = None, **kwargs):
        """
        Thin wrapper around ``nasabinning.visualizations.plot_event_rate_stability``.
        """
        from .visualizations import plot_event_rate_stability

        if pivot is None:
            pivot = getattr(self, "_pivot_", None)
        if pivot is None:
            raise ValueError(
                "Passe um pivot explicitamente ou chame stability_over_time antes de plotar."
            )
        return plot_event_rate_stability(pivot, binner=self, **kwargs)

    # ------------------------------------------------------------------
    def temporal_bin_diagnostics(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        *,
        time_col: str,
        dataset_name: str | None = None,
        min_bin_count: int = 30,
        min_bin_share: float = 0.05,
        min_time_coverage: float = 0.75,
    ) -> pd.DataFrame:
        """
        Build a detailed variable/bin/time diagnostics table for temporal analysis.
        """
        from .temporal_diagnostics import build_temporal_bin_diagnostics

        diagnostics = build_temporal_bin_diagnostics(
            self,
            X,
            y,
            time_col=time_col,
            dataset_name=dataset_name,
            min_bin_count=min_bin_count,
            min_bin_share=min_bin_share,
            min_time_coverage=min_time_coverage,
        )
        self._temporal_bin_diagnostics_ = diagnostics
        return diagnostics

    # ------------------------------------------------------------------
    def temporal_variable_summary(
        self,
        X: pd.DataFrame | None = None,
        y: pd.Series | None = None,
        *,
        diagnostics: pd.DataFrame | None = None,
        time_col: str | None = None,
        dataset_name: str | None = None,
        min_bin_count: int = 30,
        min_bin_share: float = 0.05,
        min_time_coverage: float = 0.75,
        event_rate_std_threshold: float = 0.05,
        woe_std_threshold: float = 0.5,
        bin_share_std_threshold: float = 0.05,
    ) -> pd.DataFrame:
        """
        Summarize temporal diagnostics at the variable level.
        """
        from .temporal_diagnostics import summarize_temporal_variable_stability

        if diagnostics is None:
            if X is None or y is None or time_col is None:
                raise ValueError(
                    "Passe diagnostics ou informe X, y e time_col para montar o sumario."
                )
            diagnostics = self.temporal_bin_diagnostics(
                X,
                y,
                time_col=time_col,
                dataset_name=dataset_name,
                min_bin_count=min_bin_count,
                min_bin_share=min_bin_share,
                min_time_coverage=min_time_coverage,
            )

        summary = summarize_temporal_variable_stability(
            diagnostics,
            time_col=time_col,
            event_rate_std_threshold=event_rate_std_threshold,
            woe_std_threshold=woe_std_threshold,
            bin_share_std_threshold=bin_share_std_threshold,
        )
        self._temporal_variable_summary_ = summary
        return summary

    # ------------------------------------------------------------------
    def save_report(self, path: str) -> None:
        from .reporting import save_binner_report

        save_binner_report(self, path)
