"""Core orchestration for RiskBands."""

from __future__ import annotations

import inspect
import warnings
from collections.abc import Sequence
from typing import Any

import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin

from .metrics import iv
from .objectives import resolve_score_strategy
from .refinement import refine_bins
from .strategies import get_strategy
from .utils.dtypes import search_dtypes


class Binner(BaseEstimator, TransformerMixin):
    """Fit and apply risk-oriented binning rules with pandas-friendly ergonomics."""

    def __init__(
        self,
        strategy: str = "supervised",
        max_bins: int = 6,
        max_n_bins: int | None = None,
        min_event_rate_diff: float = 0.02,
        monotonic: str | None = None,
        monotonic_trend: str | None = None,
        check_stability: bool = False,
        use_optuna: bool = False,
        time_col: str | None = None,
        force_categorical: list[str] | None = None,
        force_numeric: list[str] | None = None,
        score_strategy: str = "legacy",
        score_weights: dict | None = None,
        normalization_strategy: str = "absolute",
        woe_shrinkage_strength: float = 25.0,
        objective_kwargs: dict | None = None,
        strategy_kwargs: dict | None = None,
    ):
        if max_n_bins is not None:
            max_bins = max_n_bins
        if monotonic is not None and monotonic_trend is not None and monotonic != monotonic_trend:
            raise ValueError(
                "`monotonic` and `monotonic_trend` were both provided with different values. "
                "Pass only one of them or keep them consistent."
            )
        monotonic = monotonic if monotonic is not None else monotonic_trend

        self.strategy = strategy
        self.max_bins = max_bins
        self.max_n_bins = max_bins
        self.min_event_rate_diff = min_event_rate_diff
        self.monotonic = monotonic
        self.monotonic_trend = monotonic
        self.check_stability = check_stability
        self.use_optuna = use_optuna
        self.time_col = time_col
        self.force_categorical = force_categorical or []
        self.force_numeric = force_numeric or []
        self.objective_kwargs = objective_kwargs or {}
        resolve_score_strategy(score_strategy=score_strategy)
        if "score_strategy" in self.objective_kwargs:
            resolve_score_strategy(
                {"score_strategy": self.objective_kwargs["score_strategy"]},
                score_strategy=None,
            )
        self.score_strategy = score_strategy
        self.score_weights = score_weights
        self.normalization_strategy = normalization_strategy
        self.woe_shrinkage_strength = woe_shrinkage_strength

        strategy_kwargs = strategy_kwargs or {}
        if "strategy_kwargs" in strategy_kwargs:
            nested = strategy_kwargs.pop("strategy_kwargs")
            for key, value in nested.items():
                strategy_kwargs.setdefault(key, value)
        self.strategy_kwargs = strategy_kwargs

        self._fitted_strategy = None
        self.bin_summary = None

    # ------------------------------------------------------------------
    def get_params(self, deep: bool = True) -> dict[str, Any]:
        """Return estimator parameters, including sklearn-style aliases."""
        params = super().get_params(deep=deep)
        params["max_n_bins"] = params.get("max_bins")
        params["monotonic_trend"] = params.get("monotonic")
        return params

    # ------------------------------------------------------------------
    def set_params(self, **params):
        """Set estimator parameters, syncing friendly aliases when needed."""
        if "max_n_bins" in params and "max_bins" in params and params["max_n_bins"] != params["max_bins"]:
            raise ValueError("`max_bins` and `max_n_bins` must match when both are provided.")
        if "monotonic_trend" in params and "monotonic" in params and params["monotonic_trend"] != params["monotonic"]:
            raise ValueError(
                "`monotonic` and `monotonic_trend` must match when both are provided."
            )
        if "score_strategy" in params:
            resolve_score_strategy(score_strategy=params["score_strategy"])
        if "objective_kwargs" in params and "score_strategy" in (params["objective_kwargs"] or {}):
            resolve_score_strategy(
                {"score_strategy": params["objective_kwargs"]["score_strategy"]},
                score_strategy=None,
            )

        if "max_n_bins" in params and "max_bins" not in params:
            params["max_bins"] = params["max_n_bins"]
        if "max_bins" in params and "max_n_bins" not in params:
            params["max_n_bins"] = params["max_bins"]
        if "monotonic_trend" in params and "monotonic" not in params:
            params["monotonic"] = params["monotonic_trend"]
        if "monotonic" in params and "monotonic_trend" not in params:
            params["monotonic_trend"] = params["monotonic"]

        result = super().set_params(**params)
        self.max_n_bins = self.max_bins
        self.monotonic_trend = self.monotonic
        return result

    # ------------------------------------------------------------------
    def _numeric_strategy_kwargs(self) -> dict:
        kwargs = dict(self.strategy_kwargs)
        kwargs.pop("n_trials", None)
        kwargs.pop("objective_kwargs", None)
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
    def _coerce_force_numeric_columns(
        self,
        X: pd.DataFrame,
        *,
        columns: Sequence[str] | None = None,
    ) -> pd.DataFrame:
        forced = set(self.force_numeric or [])
        if not forced:
            return X

        candidate_columns = list(columns) if columns is not None else list(X.columns)
        present = [col for col in candidate_columns if col in forced and col in X.columns]
        if not present:
            return X

        X_numeric = X.copy()
        for col in present:
            try:
                X_numeric[col] = pd.to_numeric(X_numeric[col], errors="raise")
            except Exception as exc:
                raise ValueError(
                    f"Column '{col}' listed in force_numeric could not be converted "
                    "to numeric values."
                ) from exc
        return X_numeric

    # ------------------------------------------------------------------
    def _resolved_objective_kwargs(self, override: dict | None = None) -> dict:
        def _merge_dicts(base: dict, extra: dict) -> dict:
            for key, value in extra.items():
                if isinstance(value, dict) and isinstance(base.get(key), dict):
                    _merge_dicts(base[key], value)
                else:
                    base[key] = value
            return base

        merged = {}
        strategy_objective = dict(self.strategy_kwargs.get("objective_kwargs", {}) or {})
        explicit_objective = dict(self.objective_kwargs or {})
        if strategy_objective:
            _merge_dicts(merged, strategy_objective)
        if explicit_objective:
            _merge_dicts(merged, explicit_objective)
        if override:
            _merge_dicts(merged, dict(override))

        merged["score_strategy"] = self.score_strategy
        if self.score_weights is not None:
            merged["weights"] = dict(self.score_weights)
        if self.normalization_strategy is not None:
            merged["normalization_strategy"] = self.normalization_strategy
        if self.woe_shrinkage_strength is not None:
            merged["woe_shrinkage_strength"] = self.woe_shrinkage_strength
        return merged

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
    def _ensure_fitted(self) -> None:
        if not hasattr(self, "_per_feature_binners") or not self._per_feature_binners:
            raise RuntimeError("Binner has not been fitted yet. Call `.fit(...)` first.")

    # ------------------------------------------------------------------
    @staticmethod
    def _deduplicate_names(names: Sequence[str]) -> list[str]:
        ordered = []
        seen = set()
        for name in names:
            if name not in seen:
                ordered.append(name)
                seen.add(name)
        return ordered

    # ------------------------------------------------------------------
    @classmethod
    def _resolve_feature_selection(
        cls,
        *,
        column: str | None = None,
        columns: Sequence[str] | None = None,
        feature: str | None = None,
        features: Sequence[str] | None = None,
    ) -> list[str] | None:
        single_candidates = [value for value in (column, feature) if value is not None]
        multi_candidates = [value for value in (columns, features) if value is not None]

        if len(single_candidates) > 1 and single_candidates[0] != single_candidates[1]:
            raise ValueError("`column` and `feature` must match when both are provided.")
        if len(multi_candidates) > 1 and list(multi_candidates[0]) != list(multi_candidates[1]):
            raise ValueError("`columns` and `features` must match when both are provided.")
        if single_candidates and multi_candidates:
            raise ValueError("Use either `column`/`feature` or `columns`/`features`, not both.")

        if single_candidates:
            return [single_candidates[0]]
        if multi_candidates:
            return cls._deduplicate_names(list(multi_candidates[0]))
        return None

    # ------------------------------------------------------------------
    @staticmethod
    def _coerce_frame(
        X: pd.DataFrame | pd.Series,
        *,
        purpose: str,
        copy: bool,
        default_name: str | None = None,
    ) -> tuple[pd.DataFrame, str]:
        if isinstance(X, pd.DataFrame):
            return (X.copy() if copy else X), "dataframe"
        if isinstance(X, pd.Series):
            name = X.name or default_name
            if not name:
                raise ValueError(
                    f"A named pandas Series is required for `{purpose}`. "
                    "Rename the Series or pass a DataFrame with `column=`."
                )
            frame = X.rename(name).to_frame()
            return (frame.copy() if copy else frame), "series"
        raise TypeError(
            f"`X` must be a pandas DataFrame or Series for `{purpose}`. "
            "Examples: `fit(df, y='target')` or `fit(df['age'], y=df['target'])`."
        )

    # ------------------------------------------------------------------
    @staticmethod
    def _coerce_target_series(
        y: pd.Series | Sequence[Any] | Any,
        *,
        index: pd.Index,
        name: str = "target",
    ) -> pd.Series:
        if isinstance(y, pd.Series):
            if len(y) != len(index):
                raise ValueError(
                    f"`y` must have the same length as `X`. Expected {len(index)} values, got {len(y)}."
                )
            if y.index.equals(index):
                return y.rename(y.name or name)
            return pd.Series(y.to_numpy(), index=index, name=y.name or name)

        try:
            series = pd.Series(y, index=index, name=name)
        except Exception as exc:  # pragma: no cover - defensive
            raise TypeError(
                "`y` must be a pandas Series, an array-like object, or a target column name."
            ) from exc
        if len(series) != len(index):
            raise ValueError(
                f"`y` must have the same length as `X`. Expected {len(index)} values, got {len(series)}."
            )
        return series

    # ------------------------------------------------------------------
    def _normalize_fit_inputs(
        self,
        X: pd.DataFrame | pd.Series,
        y: pd.Series | Sequence[Any] | str | None = None,
        *,
        target: pd.Series | Sequence[Any] | str | None = None,
        column: str | None = None,
        columns: Sequence[str] | None = None,
        feature: str | None = None,
        features: Sequence[str] | None = None,
        time_col: str | None = None,
        copy: bool = True,
    ) -> tuple[pd.DataFrame, pd.Series, str, list[str], str]:
        selected_columns = self._resolve_feature_selection(
            column=column,
            columns=columns,
            feature=feature,
            features=features,
        )
        default_name = selected_columns[0] if selected_columns and len(selected_columns) == 1 else "feature"
        X_frame, input_kind = self._coerce_frame(X, purpose="fit", copy=copy, default_name=default_name)

        if isinstance(y, str):
            if target is not None and target != y:
                raise ValueError("Pass the target once: use either `y=` or `target=`.")
            target_ref = y
        elif target is not None and y is not None:
            raise ValueError("Pass the target once: use either `y=` or `target=`.")
        else:
            target_ref = target if target is not None else y

        if target_ref is None:
            raise TypeError(
                "Missing target. Pass `y` as a Series/array-like object or as a column name, "
                "for example `fit(df, y='target')`."
            )

        target_is_column = isinstance(target_ref, str)
        if target_is_column:
            if target_ref not in X_frame.columns:
                available = ", ".join(map(str, X_frame.columns.tolist()))
                raise KeyError(
                    f"Target column '{target_ref}' was not found in `X`. Available columns: {available}."
                )
            y_series = X_frame[target_ref].copy()
            target_name = target_ref
        else:
            y_series = self._coerce_target_series(target_ref, index=X_frame.index)
            target_name = y_series.name or "target"
            y_series = y_series.rename(target_name)

        if time_col is not None and time_col not in X_frame.columns:
            raise KeyError(
                f"`time_col='{time_col}'` was not found in `X`. "
                "Pass a DataFrame containing the period column or omit `time_col`."
            )
        if time_col is not None and time_col == target_name:
            raise ValueError("`time_col` cannot point to the target column.")

        feature_candidates = [
            col for col in X_frame.columns if (not target_is_column or col != target_name)
        ]
        if selected_columns is None:
            selected_features = [col for col in feature_candidates if col != time_col]
        else:
            missing = [col for col in selected_columns if col not in X_frame.columns]
            if missing:
                available = ", ".join(map(str, X_frame.columns.tolist()))
                raise KeyError(
                    f"Selected feature(s) not found in `X`: {missing}. Available columns: {available}."
                )
            if target_is_column and target_name in selected_columns:
                raise ValueError(
                    "`column`/`columns` should refer to feature columns, not to the target column."
                )
            selected_features = [col for col in selected_columns if col != time_col]

        if not selected_features:
            raise ValueError(
                "No feature columns were selected. Pass `column=`/`columns=` or provide a DataFrame "
                "with at least one feature besides the target and optional time column."
            )

        ordered_columns = self._deduplicate_names(
            selected_features + ([time_col] if time_col is not None and time_col in X_frame.columns else [])
        )
        X_selected = X_frame.loc[:, ordered_columns].copy() if copy else X_frame.loc[:, ordered_columns]
        return X_selected, y_series, target_name, selected_features, input_kind

    # ------------------------------------------------------------------
    def _normalize_transform_input(
        self,
        X: pd.DataFrame | pd.Series,
        *,
        column: str | None = None,
        columns: Sequence[str] | None = None,
        feature: str | None = None,
        features: Sequence[str] | None = None,
        copy: bool = True,
    ) -> tuple[pd.DataFrame, list[str], str]:
        self._ensure_fitted()

        selected_columns = self._resolve_feature_selection(
            column=column,
            columns=columns,
            feature=feature,
            features=features,
        )
        default_name = getattr(self, "feature_name_", None)
        X_frame, input_kind = self._coerce_frame(
            X,
            purpose="transform",
            copy=copy,
            default_name=default_name,
        )

        fitted_columns = list(getattr(self, "feature_names_in_", list(self._per_feature_binners)))
        if selected_columns is None:
            selected_columns = fitted_columns
        else:
            invalid = [col for col in selected_columns if col not in fitted_columns]
            if invalid:
                raise KeyError(
                    f"Feature(s) {invalid} were not fitted. Available fitted features: {fitted_columns}."
                )

        missing = [col for col in selected_columns if col not in X_frame.columns]
        if missing:
            raise KeyError(
                f"`X` is missing fitted feature(s): {missing}. "
                "Pass the original DataFrame, a matching subset, or use `column=`/`columns=`."
            )
        X_selected = X_frame.loc[:, selected_columns].copy() if copy else X_frame.loc[:, selected_columns]
        return X_selected, selected_columns, input_kind

    # ------------------------------------------------------------------
    @staticmethod
    def _build_summary_view(report: pd.DataFrame | None) -> pd.DataFrame:
        if report is None or report.empty:
            return pd.DataFrame()
        columns = [
            "variable",
            "n_bins",
            "iv",
            "temporal_score",
            "score_strategy",
            "objective_direction",
            "objective_score",
            "objective_preference_score",
            "coverage_ratio_min",
            "coverage_ratio_mean",
            "rare_bin_count",
            "ranking_reversal_period_count",
            "selection_basis",
            "alert_flags",
        ]
        available = [column for column in columns if column in report.columns]
        return report.loc[:, available].copy()

    # ------------------------------------------------------------------
    @staticmethod
    def _build_score_details_view(report: pd.DataFrame | None) -> pd.DataFrame:
        if report is None or report.empty:
            return pd.DataFrame()

        fixed_columns = [
            "variable",
            "score_strategy",
            "objective_direction",
            "objective_score",
            "objective_preference_score",
            "objective_base_score",
            "objective_total_penalty",
            "objective_normalization_strategy",
            "woe_shrinkage_strength",
        ]
        dynamic_columns = [
            column
            for column in report.columns
            if column.startswith("objective_raw_")
            or column.startswith("objective_norm_")
            or column.startswith("objective_weight_")
        ]
        available = [column for column in fixed_columns if column in report.columns] + dynamic_columns
        return report.loc[:, available].copy()

    # ------------------------------------------------------------------
    @staticmethod
    def _collapse_metric(score_details: pd.DataFrame, column: str):
        if score_details.empty or column not in score_details.columns:
            return None
        series = (
            score_details.set_index("variable")[column]
            if "variable" in score_details.columns
            else score_details[column]
        )
        series = pd.to_numeric(series, errors="coerce").dropna()
        if series.empty:
            return None
        if len(series) == 1:
            return float(series.iloc[0])
        return series

    # ------------------------------------------------------------------
    @staticmethod
    def _prepare_binning_summary(summary: pd.DataFrame) -> pd.DataFrame:
        summary = summary.copy().reset_index(drop=True)
        if "bin_order" not in summary.columns:
            summary["bin_order"] = range(len(summary))
        if "bin_code" not in summary.columns:
            summary["bin_code"] = summary["bin_order"].astype(float)
        return summary

    # ------------------------------------------------------------------
    @staticmethod
    def _profile_from_columns(row: pd.Series, prefix: str) -> str:
        items = []
        for column, value in row.items():
            if not column.startswith(prefix):
                continue
            score = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
            if pd.isna(score):
                continue
            items.append((column.replace(prefix, ""), float(score)))
        if not items:
            return ""
        items.sort(key=lambda item: abs(item[1]), reverse=True)
        return "; ".join(f"{name}={value:.3f}" for name, value in items)

    # ------------------------------------------------------------------
    @classmethod
    def _build_score_table_view(cls, report: pd.DataFrame | None) -> pd.DataFrame:
        if report is None or report.empty:
            return pd.DataFrame()

        table = report.copy()
        table["weight_profile"] = table.apply(
            lambda row: cls._profile_from_columns(row, "objective_weight_"),
            axis=1,
        )
        table["normalized_component_profile"] = table.apply(
            lambda row: cls._profile_from_columns(row, "objective_norm_"),
            axis=1,
        )
        table["raw_component_profile"] = table.apply(
            lambda row: cls._profile_from_columns(row, "objective_raw_"),
            axis=1,
        )

        fixed_columns = [
            "variable",
            "score_strategy",
            "objective_direction",
            "objective_score",
            "objective_preference_score",
            "objective_base_score",
            "objective_total_penalty",
            "objective_normalization_strategy",
            "woe_shrinkage_strength",
            "selection_basis",
            "weight_profile",
            "normalized_component_profile",
            "raw_component_profile",
            "key_drivers",
            "key_penalties",
            "alert_flags",
        ]
        dynamic_columns = [
            column
            for column in table.columns
            if column.startswith("objective_weight_")
            or column.startswith("objective_norm_")
            or column.startswith("objective_raw_")
        ]
        ordered = [column for column in fixed_columns if column in table.columns]
        ordered.extend(column for column in dynamic_columns if column not in ordered)
        return table.loc[:, ordered].copy()

    # ------------------------------------------------------------------
    @classmethod
    def _build_audit_table_view(cls, report: pd.DataFrame | None) -> pd.DataFrame:
        if report is None or report.empty:
            return pd.DataFrame()

        table = report.copy()
        table["weight_profile"] = table.apply(
            lambda row: cls._profile_from_columns(row, "objective_weight_"),
            axis=1,
        )
        fixed_columns = [
            "dataset",
            "variable",
            "candidate_name",
            "selected_strategy",
            "cut_summary",
            "n_bins",
            "iv",
            "temporal_score",
            "score_strategy",
            "objective_direction",
            "objective_score",
            "objective_preference_score",
            "objective_total_penalty",
            "weight_profile",
            "coverage_ratio_min",
            "coverage_ratio_mean",
            "rare_bin_count",
            "ranking_reversal_period_count",
            "selection_basis",
            "alert_flags",
            "key_drivers",
            "key_penalties",
            "rationale_summary",
        ]
        dynamic_columns = [
            column
            for column in table.columns
            if column not in fixed_columns
        ]
        ordered = [column for column in fixed_columns if column in table.columns]
        ordered.extend(column for column in dynamic_columns if column not in ordered)
        return table.loc[:, ordered].copy()

    # ------------------------------------------------------------------
    def _refresh_cached_outputs(
        self,
        X: pd.DataFrame | None = None,
        y: pd.Series | None = None,
        *,
        time_col: str | None = None,
    ) -> None:
        self.binning_table_ = self.binning_table()
        self.bins_ = {
            variable: self.binning_table(column=variable)
            for variable in getattr(self, "feature_names_in_", [])
        }
        from .reporting import build_binner_metadata

        self.metadata_ = build_binner_metadata(self, time_col=time_col)

        report = None
        report_error = None
        for kwargs in (
            {
                "X": X,
                "y": y,
                "time_col": time_col,
                "dataset_name": "fit",
                "refresh": True,
            },
            {"refresh": True},
        ):
            try:
                report = self.report(**kwargs)
                break
            except Exception as exc:  # pragma: no cover - defensive fallback
                report_error = exc

        if report is None:
            warnings.warn(
                "RiskBands could not build cached report artifacts after fit. "
                f"You can still call `report(...)` manually. Details: {report_error}",
                RuntimeWarning,
            )
            report = pd.DataFrame()

        self.report_ = report
        self.summary_ = self._build_summary_view(report)
        self.score_details_ = self._build_score_details_view(report)
        self.score_table_ = self._build_score_table_view(report)
        self.audit_table_ = self._build_audit_table_view(report)
        self.score_ = self._collapse_metric(self.score_details_, "objective_score")
        self.comparison_score_ = self._collapse_metric(
            self.score_details_,
            "objective_preference_score",
        )
        self.diagnostics_ = getattr(self, "_temporal_bin_diagnostics_", None)

    # ------------------------------------------------------------------
    def fit(
        self,
        X: pd.DataFrame | pd.Series,
        y: pd.Series | Sequence[Any] | str | None = None,
        *,
        target: pd.Series | Sequence[Any] | str | None = None,
        column: str | None = None,
        columns: Sequence[str] | None = None,
        feature: str | None = None,
        features: Sequence[str] | None = None,
        time_col: str | None = None,
        copy: bool = True,
    ):
        """Fit binning rules on one or more columns."""
        time_col = time_col or self.time_col
        X, y, target_name, selected_features, input_kind = self._normalize_fit_inputs(
            X,
            y,
            target=target,
            column=column,
            columns=columns,
            feature=feature,
            features=features,
            time_col=time_col,
            copy=copy,
        )

        self.time_col = time_col
        X_features = X.drop(columns=[time_col], errors="ignore") if time_col else X.copy()

        num_cols, cat_cols = search_dtypes(
            pd.concat([X_features, y.rename("target")], axis=1),
            target_col="target",
            limite_categorico=50,
            force_categorical=self.force_categorical,
            force_numeric=self.force_numeric,
            verbose=False,
        )
        X_features = self._coerce_force_numeric_columns(X_features, columns=num_cols)

        self.numeric_cols_ = num_cols
        self.cat_cols_ = cat_cols
        self.time_cols_ = [time_col] if time_col and time_col in X.columns else []
        self.ignored_cols_ = [c for c in X_features.columns if c not in num_cols + cat_cols]
        self.feature_names_in_ = list(X_features.columns)
        self.columns_ = list(self.feature_names_in_)
        self.feature_name_ = self.feature_names_in_[0] if len(self.feature_names_in_) == 1 else None
        self.target_name_ = target_name
        self.input_type_ = input_kind
        self.n_features_in_ = len(self.feature_names_in_)
        self.selected_columns_ = list(selected_features)

        if self.use_optuna:
            if self.strategy != "supervised":
                raise ValueError("Optuna is currently supported only for strategy='supervised'.")

            from .optuna_optimizer import optimize_bins

            optuna_kwargs = dict(self.strategy_kwargs)
            n_trials = optuna_kwargs.pop("n_trials", 20)
            sampler_seed = optuna_kwargs.pop("sampler_seed", None)
            if sampler_seed is None:
                sampler_seed = optuna_kwargs.pop("random_state", None)
            objective_kwargs = self._resolved_objective_kwargs(optuna_kwargs.pop("objective_kwargs", None))
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
                feature_base_kwargs = dict(base_kwargs)
                if col in self.force_numeric:
                    feature_base_kwargs["force_numeric"] = [col]
                if col in self.force_categorical:
                    feature_base_kwargs["force_categorical"] = [col]
                best, fitted_binner = optimize_bins(
                    X_features[[col]],
                    y,
                    time_col=time_col,
                    time_values=time_values,
                    n_trials=n_trials,
                    sampler_seed=sampler_seed,
                    objective_kwargs=objective_kwargs,
                    **feature_base_kwargs,
                )
                self._per_feature_binners[col] = fitted_binner
                self.best_params_[col] = best
                self.objective_summaries_[col] = getattr(fitted_binner, "objective_summary_", None)

            self.bin_summary = pd.concat(
                [binner.bin_summary for binner in self._per_feature_binners.values()],
                ignore_index=True,
            )
            self.bin_summary = pd.concat(
                [
                    self._prepare_binning_summary(group)
                    for _, group in self.bin_summary.groupby("variable", sort=False)
                ],
                ignore_index=True,
            )
            self._compute_iv_metrics()
            if self.objective_summaries_:
                self.objective_summary_ = next(iter(self.objective_summaries_.values()))
                self.objective_config_ = next(
                    (
                        getattr(binner, "objective_config_", None)
                        for binner in self._per_feature_binners.values()
                        if getattr(binner, "objective_config_", None) is not None
                    ),
                    None,
                )
            self._refresh_cached_outputs(X, y, time_col=time_col)
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
            summary = self._prepare_binning_summary(summary)

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
            summary = self._prepare_binning_summary(summary)

            self._per_feature_binners[col] = strat
            summaries.append(summary)

        self.bin_summary = pd.concat(summaries, ignore_index=True)
        self.bin_summary = pd.concat(
            [
                self._prepare_binning_summary(group)
                for _, group in self.bin_summary.groupby("variable", sort=False)
            ],
            ignore_index=True,
        )
        self._compute_iv_metrics()
        from .objectives import resolve_objective_config

        self.objective_config_ = resolve_objective_config(self._resolved_objective_kwargs())
        self._refresh_cached_outputs(X, y, time_col=time_col)
        return self

    # ------------------------------------------------------------------
    def transform(
        self,
        X: pd.DataFrame | pd.Series,
        *,
        column: str | None = None,
        columns: Sequence[str] | None = None,
        feature: str | None = None,
        features: Sequence[str] | None = None,
        return_woe: bool = False,
        return_type: str = "auto",
        copy: bool = True,
    ):
        """Apply fitted bins to new data."""
        X, selected_columns, input_kind = self._normalize_transform_input(
            X,
            column=column,
            columns=columns,
            feature=feature,
            features=features,
            copy=copy,
        )
        X = self._coerce_force_numeric_columns(X, columns=selected_columns)

        out = {}
        for col in selected_columns:
            binner = self._per_feature_binners[col]
            sig = inspect.signature(binner.transform)
            kwargs = {"return_woe": return_woe} if "return_woe" in sig.parameters else {}
            transformed = binner.transform(X[[col]], **kwargs)
            out[col] = transformed if isinstance(transformed, pd.Series) else transformed[col]

        transformed_df = pd.DataFrame(out, index=X.index)
        if return_type == "dataframe":
            return transformed_df
        if return_type == "series":
            if transformed_df.shape[1] != 1:
                raise ValueError("`return_type='series'` requires a single selected feature.")
            return transformed_df.iloc[:, 0].rename(transformed_df.columns[0])
        if return_type != "auto":
            raise ValueError("`return_type` must be one of: 'auto', 'series', or 'dataframe'.")
        if input_kind == "series":
            return transformed_df.iloc[:, 0].rename(transformed_df.columns[0])
        return transformed_df

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
    def fit_transform(
        self,
        X: pd.DataFrame | pd.Series,
        y: pd.Series | Sequence[Any] | str | None = None,
        *,
        target: pd.Series | Sequence[Any] | str | None = None,
        column: str | None = None,
        columns: Sequence[str] | None = None,
        feature: str | None = None,
        features: Sequence[str] | None = None,
        time_col: str | None = None,
        return_woe: bool = False,
        return_type: str = "auto",
        copy: bool = True,
    ):
        """Fit the binner and return the transformed result in one step."""
        return self.fit(
            X,
            y,
            target=target,
            column=column,
            columns=columns,
            feature=feature,
            features=features,
            time_col=time_col,
            copy=copy,
        ).transform(
            X,
            column=column,
            columns=columns,
            feature=feature,
            features=features,
            return_woe=return_woe,
            return_type=return_type,
            copy=copy,
        )

    # ------------------------------------------------------------------
    def binning_table(
        self,
        *,
        column: str | None = None,
        columns: Sequence[str] | None = None,
        feature: str | None = None,
        features: Sequence[str] | None = None,
    ) -> pd.DataFrame:
        """Return the fitted bin table as a pandas DataFrame."""
        self._ensure_fitted()
        if self.bin_summary is None:
            return pd.DataFrame()

        selected_columns = self._resolve_feature_selection(
            column=column,
            columns=columns,
            feature=feature,
            features=features,
        )
        table = self.bin_summary.copy()
        if selected_columns is not None:
            table = table.loc[table["variable"].isin(selected_columns)].reset_index(drop=True)
        return table

    # ------------------------------------------------------------------
    def feature_binning_table(
        self,
        *,
        column: str | None = None,
        columns: Sequence[str] | None = None,
        feature: str | None = None,
        features: Sequence[str] | None = None,
    ) -> pd.DataFrame:
        """Friendly alias for :meth:`binning_table`."""
        return self.binning_table(
            column=column,
            columns=columns,
            feature=feature,
            features=features,
        )

    # ------------------------------------------------------------------
    def get_binning_table(
        self,
        *,
        column: str | None = None,
        columns: Sequence[str] | None = None,
        feature: str | None = None,
        features: Sequence[str] | None = None,
    ) -> pd.DataFrame:
        """Alias for :meth:`binning_table` aimed at discoverability."""
        return self.binning_table(
            column=column,
            columns=columns,
            feature=feature,
            features=features,
        )

    # ------------------------------------------------------------------
    def diagnostics(
        self,
        X: pd.DataFrame | pd.Series | None = None,
        y: pd.Series | Sequence[Any] | str | None = None,
        *,
        target: pd.Series | Sequence[Any] | str | None = None,
        time_col: str | None = None,
        dataset_name: str | None = None,
        kind: str = "bin",
        refresh: bool = False,
        min_bin_count: int = 30,
        min_bin_share: float = 0.05,
        min_time_coverage: float = 0.75,
        event_rate_std_threshold: float = 0.05,
        woe_std_threshold: float = 0.5,
        bin_share_std_threshold: float = 0.05,
    ) -> pd.DataFrame:
        """Return cached temporal diagnostics or compute them from pandas inputs."""
        if kind not in {"bin", "variable"}:
            raise ValueError("`kind` must be either 'bin' or 'variable'.")

        cached = (
            getattr(self, "_temporal_bin_diagnostics_", None)
            if kind == "bin"
            else getattr(self, "_temporal_variable_summary_", None)
        )
        if not refresh and X is None and y is None and target is None and cached is not None:
            return cached

        time_col = time_col or self.time_col
        if time_col is None:
            raise ValueError(
                "Temporal diagnostics require `time_col`. Pass `time_col=` or fit the binner "
                "with a time column before calling `diagnostics()`."
            )
        if X is None:
            raise ValueError(
                "Temporal diagnostics are not cached. Pass `X`, `y`, and `time_col`, or call "
                "`temporal_bin_diagnostics(...)` first."
            )

        X_eval, y_eval, _, _, _ = self._normalize_fit_inputs(
            X,
            y,
            target=target,
            time_col=time_col,
            copy=False,
        )
        if kind == "bin":
            return self.temporal_bin_diagnostics(
                X_eval,
                y_eval,
                time_col=time_col,
                dataset_name=dataset_name,
                min_bin_count=min_bin_count,
                min_bin_share=min_bin_share,
                min_time_coverage=min_time_coverage,
            )
        return self.temporal_variable_summary(
            X_eval,
            y_eval,
            time_col=time_col,
            dataset_name=dataset_name,
            min_bin_count=min_bin_count,
            min_bin_share=min_bin_share,
            min_time_coverage=min_time_coverage,
            event_rate_std_threshold=event_rate_std_threshold,
            woe_std_threshold=woe_std_threshold,
            bin_share_std_threshold=bin_share_std_threshold,
        )

    # ------------------------------------------------------------------
    def report(
        self,
        X: pd.DataFrame | pd.Series | None = None,
        y: pd.Series | Sequence[Any] | str | None = None,
        *,
        target: pd.Series | Sequence[Any] | str | None = None,
        time_col: str | None = None,
        dataset_name: str | None = None,
        diagnostics: pd.DataFrame | None = None,
        summary: pd.DataFrame | None = None,
        candidate_name: str | None = None,
        objective_kwargs: dict | None = None,
        refresh: bool = False,
    ) -> pd.DataFrame:
        """Return a variable-level auditable report."""
        if (
            not refresh
            and X is None
            and y is None
            and target is None
            and diagnostics is None
            and summary is None
            and objective_kwargs is None
        ):
            cached = getattr(self, "_variable_audit_report_", None)
            if cached is not None:
                return cached

        X_eval = None
        y_eval = None
        if X is not None or y is not None or target is not None:
            X_eval, y_eval, _, _, _ = self._normalize_fit_inputs(
                X,
                y,
                target=target,
                time_col=time_col or self.time_col,
                copy=False,
            )
        return self.variable_audit_report(
            X_eval,
            y_eval,
            time_col=time_col or self.time_col,
            dataset_name=dataset_name,
            diagnostics=diagnostics,
            summary=summary,
            candidate_name=candidate_name,
            objective_kwargs=objective_kwargs,
        )

    # ------------------------------------------------------------------
    def summary(
        self,
        X: pd.DataFrame | pd.Series | None = None,
        y: pd.Series | Sequence[Any] | str | None = None,
        *,
        target: pd.Series | Sequence[Any] | str | None = None,
        time_col: str | None = None,
        dataset_name: str | None = None,
        refresh: bool = False,
    ) -> pd.DataFrame:
        """Return a concise, notebook-friendly summary view."""
        if not refresh and X is None and y is None and target is None and hasattr(self, "summary_"):
            return self.summary_
        report = self.report(
            X,
            y,
            target=target,
            time_col=time_col,
            dataset_name=dataset_name,
            refresh=refresh,
        )
        summary = self._build_summary_view(report)
        self.summary_ = summary
        return summary

    # ------------------------------------------------------------------
    def score_details(
        self,
        X: pd.DataFrame | pd.Series | None = None,
        y: pd.Series | Sequence[Any] | str | None = None,
        *,
        target: pd.Series | Sequence[Any] | str | None = None,
        time_col: str | None = None,
        dataset_name: str | None = None,
        refresh: bool = False,
    ) -> pd.DataFrame:
        """Return the detailed score breakdown exposed by the current objective."""
        if not refresh and X is None and y is None and target is None and hasattr(self, "score_details_"):
            return self.score_details_
        report = self.report(
            X,
            y,
            target=target,
            time_col=time_col,
            dataset_name=dataset_name,
            refresh=refresh,
        )
        score_details = self._build_score_details_view(report)
        self.score_details_ = score_details
        self.score_ = self._collapse_metric(score_details, "objective_score")
        self.comparison_score_ = self._collapse_metric(
            score_details,
            "objective_preference_score",
        )
        return score_details

    # ------------------------------------------------------------------
    def score_table(
        self,
        X: pd.DataFrame | pd.Series | None = None,
        y: pd.Series | Sequence[Any] | str | None = None,
        *,
        target: pd.Series | Sequence[Any] | str | None = None,
        time_col: str | None = None,
        dataset_name: str | None = None,
        refresh: bool = False,
    ) -> pd.DataFrame:
        """Return a notebook-friendly score breakdown with weights and diagnostics."""
        if not refresh and X is None and y is None and target is None and hasattr(self, "score_table_"):
            return self.score_table_
        report = self.report(
            X,
            y,
            target=target,
            time_col=time_col,
            dataset_name=dataset_name,
            refresh=refresh,
        )
        score_table = self._build_score_table_view(report)
        self.score_table_ = score_table
        return score_table

    # ------------------------------------------------------------------
    def audit_table(
        self,
        X: pd.DataFrame | pd.Series | None = None,
        y: pd.Series | Sequence[Any] | str | None = None,
        *,
        target: pd.Series | Sequence[Any] | str | None = None,
        time_col: str | None = None,
        dataset_name: str | None = None,
        refresh: bool = False,
    ) -> pd.DataFrame:
        """Return a consolidated audit table with cuts, score, and temporal diagnostics."""
        if not refresh and X is None and y is None and target is None and hasattr(self, "audit_table_"):
            return self.audit_table_
        report = self.report(
            X,
            y,
            target=target,
            time_col=time_col,
            dataset_name=dataset_name,
            refresh=refresh,
        )
        audit_table = self._build_audit_table_view(report)
        self.audit_table_ = audit_table
        return audit_table

    # ------------------------------------------------------------------
    def plot_stability(
        self,
        X: pd.DataFrame | pd.Series | None = None,
        y: pd.Series | Sequence[Any] | str | None = None,
        *,
        target: pd.Series | Sequence[Any] | str | None = None,
        time_col: str | None = None,
        pivot: pd.DataFrame | None = None,
        fill_value: float | None = None,
        column: str | None = None,
        columns: Sequence[str] | None = None,
        feature: str | None = None,
        features: Sequence[str] | None = None,
        refresh: bool = False,
        **kwargs,
    ):
        """Plot event-rate stability with a pandas-friendly wrapper."""
        if pivot is None and not refresh:
            pivot = getattr(self, "_pivot_", None)

        if pivot is None:
            time_col = time_col or self.time_col
            if time_col is None:
                raise ValueError(
                    "Pass `time_col=` together with `X` and `y`, or call `stability_over_time(...)` first."
                )
            if X is None:
                raise ValueError(
                    "No cached stability pivot is available. Pass `X`, `y`, and `time_col` to compute one."
                )
            X_eval, y_eval, _, _, _ = self._normalize_fit_inputs(
                X,
                y,
                target=target,
                time_col=time_col,
                copy=False,
            )
            pivot = self.stability_over_time(
                X_eval,
                y_eval,
                time_col=time_col,
                fill_value=fill_value,
            )

        selected_columns = self._resolve_feature_selection(
            column=column,
            columns=columns,
            feature=feature,
            features=features,
        )
        if selected_columns is not None and not pivot.empty:
            level = "variable" if "variable" in pivot.index.names else pivot.index.names[0]
            mask = pivot.index.get_level_values(level).isin(selected_columns)
            pivot = pivot.loc[mask]
        return self.plot_event_rate_stability(pivot=pivot, **kwargs)

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

        if hasattr(binner_col, "category_mapping_"):
            mapping = binner_col.category_mapping_
            return (
                pd.DataFrame(
                    {
                        "categoria": list(mapping.keys()),
                        "bin": list(mapping.values()),
                    }
                )
                .sort_values(["bin", "categoria"], kind="mergesort")
                .reset_index(drop=True)
            )

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

        diagnostics = self.temporal_bin_diagnostics(
            X,
            y,
            time_col=time_col,
            dataset_name="stability_over_time",
        )
        pivot = (
            diagnostics.pivot_table(
                index=["variable", "bin"],
                columns=time_col,
                values="event_rate",
                aggfunc="first",
            )
            .sort_index(axis=1)
            .sort_index()
        )
        if fill_value is not None:
            pivot = pivot.fillna(fill_value)
        self._pivot_ = pivot
        self._stability_table_ = diagnostics
        return pivot

    # ------------------------------------------------------------------
    def _bin_code_to_label(self, var: str) -> dict:
        """
        Return a mapping {bin_code -> interval label} for the given feature.
        """
        bs = self.bin_summary.loc[self.bin_summary["variable"] == var].copy()

        for candidate in ("bin_order", "bin_code", "bin_code_float", "bin_code_int"):
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
        Thin wrapper around ``riskbands.visualizations.plot_event_rate_stability``.
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
    def _resolve_plot_diagnostics(
        self,
        X: pd.DataFrame | pd.Series | None,
        y: pd.Series | Sequence[Any] | str | None,
        *,
        target: pd.Series | Sequence[Any] | str | None = None,
        time_col: str | None = None,
        dataset_name: str | None = None,
        column: str | None = None,
        columns: Sequence[str] | None = None,
        feature: str | None = None,
        features: Sequence[str] | None = None,
        refresh: bool = False,
    ) -> tuple[pd.DataFrame, str]:
        diagnostics = self.diagnostics(
            X,
            y,
            target=target,
            time_col=time_col,
            dataset_name=dataset_name,
            kind="bin",
            refresh=refresh,
        )
        resolved_time_col = time_col or diagnostics.attrs.get("time_col") or self.time_col
        selected_columns = self._resolve_feature_selection(
            column=column,
            columns=columns,
            feature=feature,
            features=features,
        )
        if selected_columns is not None and not diagnostics.empty:
            diagnostics = diagnostics.loc[diagnostics["variable"].isin(selected_columns)].reset_index(
                drop=True
            )
        return diagnostics, resolved_time_col

    # ------------------------------------------------------------------
    def plot_bad_rate_over_time(
        self,
        X: pd.DataFrame | pd.Series | None = None,
        y: pd.Series | Sequence[Any] | str | None = None,
        *,
        target: pd.Series | Sequence[Any] | str | None = None,
        time_col: str | None = None,
        dataset_name: str | None = None,
        column: str | None = None,
        columns: Sequence[str] | None = None,
        feature: str | None = None,
        features: Sequence[str] | None = None,
        refresh: bool = False,
        title_prefix: str | None = "Bad rate por bin ao longo do tempo",
        figsize: tuple[float, float] = (13.5, 6.5),
    ):
        """Plot bad rate by bin over time with a notebook-friendly public API."""
        from .visualizations import plot_metric_over_time

        diagnostics, resolved_time_col = self._resolve_plot_diagnostics(
            X,
            y,
            target=target,
            time_col=time_col,
            dataset_name=dataset_name,
            column=column,
            columns=columns,
            feature=feature,
            features=features,
            refresh=refresh,
        )
        return plot_metric_over_time(
            diagnostics,
            time_col=resolved_time_col,
            value_col="event_rate",
            title_prefix=title_prefix,
            ylabel="Bad rate (%)",
            legend_title="Bin",
            percent=True,
            figsize=figsize,
        )

    # ------------------------------------------------------------------
    def plot_bad_rate_heatmap(
        self,
        X: pd.DataFrame | pd.Series | None = None,
        y: pd.Series | Sequence[Any] | str | None = None,
        *,
        target: pd.Series | Sequence[Any] | str | None = None,
        time_col: str | None = None,
        dataset_name: str | None = None,
        column: str | None = None,
        columns: Sequence[str] | None = None,
        feature: str | None = None,
        features: Sequence[str] | None = None,
        refresh: bool = False,
        title_prefix: str | None = "Heatmap de bad rate por bin e safra",
        figsize: tuple[float, float] = (12.5, 6.0),
        annotate: bool = True,
    ):
        """Plot a bad-rate heatmap without requiring manual pivot logic."""
        from .visualizations import plot_metric_heatmap

        diagnostics, resolved_time_col = self._resolve_plot_diagnostics(
            X,
            y,
            target=target,
            time_col=time_col,
            dataset_name=dataset_name,
            column=column,
            columns=columns,
            feature=feature,
            features=features,
            refresh=refresh,
        )
        return plot_metric_heatmap(
            diagnostics,
            time_col=resolved_time_col,
            value_col="event_rate",
            title_prefix=title_prefix,
            colorbar_label="Bad rate (%)",
            percent=True,
            figsize=figsize,
            annotate=annotate,
        )

    # ------------------------------------------------------------------
    def plot_bin_share_over_time(
        self,
        X: pd.DataFrame | pd.Series | None = None,
        y: pd.Series | Sequence[Any] | str | None = None,
        *,
        target: pd.Series | Sequence[Any] | str | None = None,
        time_col: str | None = None,
        dataset_name: str | None = None,
        column: str | None = None,
        columns: Sequence[str] | None = None,
        feature: str | None = None,
        features: Sequence[str] | None = None,
        refresh: bool = False,
        title_prefix: str | None = "Share dos bins ao longo do tempo",
        figsize: tuple[float, float] = (13.5, 6.5),
    ):
        """Plot bin share trajectories over time to highlight sparse or unstable bins."""
        from .visualizations import plot_metric_over_time

        diagnostics, resolved_time_col = self._resolve_plot_diagnostics(
            X,
            y,
            target=target,
            time_col=time_col,
            dataset_name=dataset_name,
            column=column,
            columns=columns,
            feature=feature,
            features=features,
            refresh=refresh,
        )
        return plot_metric_over_time(
            diagnostics,
            time_col=resolved_time_col,
            value_col="bin_share",
            title_prefix=title_prefix,
            ylabel="Bin share (%)",
            legend_title="Bin",
            percent=True,
            figsize=figsize,
        )

    # ------------------------------------------------------------------
    def plot_score_components(
        self,
        *,
        column: str | None = None,
        feature: str | None = None,
        title: str | None = None,
        figsize: tuple[float, float] = (13.5, 7.5),
    ):
        """Plot weighted objective components and score weights for one fitted feature."""
        from .visualizations import plot_score_components

        selected = self._resolve_feature_selection(column=column, feature=feature)
        score_table = self.score_table()
        audit_table = self.audit_table()
        if score_table.empty:
            raise ValueError("No score table is available. Fit the binner before plotting score components.")
        feature_name = (
            selected[0]
            if selected is not None
            else score_table["variable"].iloc[0]
        )
        score_row = score_table.loc[score_table["variable"] == feature_name]
        audit_row = audit_table.loc[audit_table["variable"] == feature_name]
        if score_row.empty:
            raise KeyError(f"Feature '{feature_name}' was not found in the fitted score table.")
        return plot_score_components(
            score_row.iloc[0],
            audit_row.iloc[0] if not audit_row.empty else None,
            title=title,
            figsize=figsize,
        )

    # ------------------------------------------------------------------
    def plot_event_rate_by_bin(
        self,
        *,
        column: str | None = None,
        feature: str | None = None,
        title: str | None = None,
        figsize: tuple[float, float] = (11.5, 5.5),
    ):
        """Plot event rate by fitted bin for one feature."""
        from .visualizations import plot_bin_summary_metric

        selected = self._resolve_feature_selection(column=column, feature=feature)
        feature_name = (
            selected[0]
            if selected is not None
            else (self.feature_name_ or self.feature_names_in_[0])
        )
        table = self.binning_table(column=feature_name)
        return plot_bin_summary_metric(
            table,
            feature_name=feature_name,
            value_col="event_rate",
            ylabel="Event rate (%)",
            title=title or f"Event rate por bin - {feature_name}",
            percent=True,
            figsize=figsize,
        )

    # ------------------------------------------------------------------
    def plot_woe(
        self,
        X: pd.DataFrame | pd.Series | None = None,
        y: pd.Series | Sequence[Any] | str | None = None,
        *,
        target: pd.Series | Sequence[Any] | str | None = None,
        time_col: str | None = None,
        dataset_name: str | None = None,
        column: str | None = None,
        feature: str | None = None,
        refresh: bool = False,
        title: str | None = None,
        figsize: tuple[float, float] = (11.5, 5.5),
    ):
        """Plot average WoE by bin using the temporal diagnostics layer."""
        from .visualizations import plot_bin_diagnostics_metric

        diagnostics, _ = self._resolve_plot_diagnostics(
            X,
            y,
            target=target,
            time_col=time_col,
            dataset_name=dataset_name,
            column=column,
            feature=feature,
            refresh=refresh,
        )
        if diagnostics.empty:
            raise ValueError("WoE plotting requires temporal diagnostics for at least one feature.")
        feature_name = (
            diagnostics["variable"].iloc[0]
            if column is None and feature is None
            else (column or feature)
        )
        return plot_bin_diagnostics_metric(
            diagnostics.loc[diagnostics["variable"] == feature_name].reset_index(drop=True),
            feature_name=feature_name,
            value_col="woe",
            ylabel="WoE",
            title=title or f"WoE medio por bin - {feature_name}",
            percent=False,
            figsize=figsize,
        )

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
        self.diagnostics_ = diagnostics
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
    def variable_audit_report(
        self,
        X: pd.DataFrame | None = None,
        y: pd.Series | None = None,
        *,
        time_col: str | None = None,
        dataset_name: str | None = None,
        diagnostics: pd.DataFrame | None = None,
        summary: pd.DataFrame | None = None,
        candidate_name: str | None = None,
        objective_kwargs: dict | None = None,
    ) -> pd.DataFrame:
        """
        Build a consolidated, auditable report of the selected bins by variable.
        """
        from .reporting import build_variable_audit_report

        return build_variable_audit_report(
            self,
            X,
            y,
            time_col=time_col,
            dataset_name=dataset_name,
            diagnostics=diagnostics,
            summary=summary,
            candidate_name=candidate_name,
            objective_kwargs=objective_kwargs,
        )

    # ------------------------------------------------------------------
    def export_binnings_json(self, path: str) -> None:
        """Export the fitted binnings as a single human-readable JSON artifact."""
        from .reporting import export_binnings_json

        self._ensure_fitted()
        export_binnings_json(self, path)

    # ------------------------------------------------------------------
    def export_bundle(self, path: str) -> None:
        """Export a complete audit bundle with JSON and tabular artifacts."""
        from .reporting import export_binner_bundle

        self._ensure_fitted()
        export_binner_bundle(self, path)

    # ------------------------------------------------------------------
    def save_report(self, path: str) -> None:
        from .reporting import save_binner_report

        save_binner_report(self, path)
