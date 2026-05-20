"""Core orchestration for RiskBands."""

from __future__ import annotations

import inspect
import math
import warnings
from collections.abc import Sequence
from numbers import Integral, Real
from typing import Any

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin

from .metrics import iv
from .objectives import resolve_score_strategy
from .refinement import refine_bins
from .strategies import get_strategy
from .utils.dataframe_backend import detect_dataframe_backend
from .utils.dtypes import search_dtypes

_MAX_PROFILE_ROWS_TO_COLLECT = 100_000
_STANDARD_MISSING_POLICY = "standard"
_SEPARATE_BIN_MISSING_POLICY = "separate_bin"
_FORBID_MISSING_POLICY = "forbid"
_MERGE_MISSING_POLICY = "merge"
_LEGACY_POLICY_ALIAS = "legacy"
_VALID_MISSING_POLICIES = {
    _STANDARD_MISSING_POLICY,
    _SEPARATE_BIN_MISSING_POLICY,
    _FORBID_MISSING_POLICY,
    _MERGE_MISSING_POLICY,
}
_NEAREST_EVENT_RATE_MISSING_MERGE_CRITERION = "nearest_event_rate"
_NEAREST_WOE_MISSING_MERGE_CRITERION = "nearest_woe"
_VALID_MISSING_MERGE_CRITERIA = {
    _NEAREST_EVENT_RATE_MISSING_MERGE_CRITERION,
    _NEAREST_WOE_MISSING_MERGE_CRITERION,
}
_SEPARATE_BIN_MISSING_MERGE_FALLBACK = "separate_bin"
_RAISE_MISSING_MERGE_FALLBACK = "raise"
_VALID_MISSING_MERGE_FALLBACKS = {
    _SEPARATE_BIN_MISSING_MERGE_FALLBACK,
    _RAISE_MISSING_MERGE_FALLBACK,
}
_PYSPARK_MISSING_MERGE_SAMPLED_FIT_CAVEAT = (
    "missing_policy='merge' Spark fit uses a controlled sampled-to-pandas path; "
    "any missing merge destination is learned only from the sampled fit rows, not from the full Spark DataFrame."
)


class Binner(BaseEstimator, TransformerMixin):
    """Fit and apply risk-oriented binning rules with pandas-friendly ergonomics."""

    def __init__(
        self,
        strategy: str = "supervised",
        max_bins: int = 6,
        max_n_bins: int | None = None,
        min_n_bins: int | None = None,
        sample_size: int | float = 10_000,
        min_event_rate_diff: float = 0.02,
        monotonic: str | None = None,
        monotonic_trend: str | None = None,
        check_stability: bool = False,
        use_optuna: bool = False,
        time_col: str | None = None,
        force_categorical: list[str] | None = None,
        force_numeric: list[str] | None = None,
        missing_policy: str = "standard",
        missing_merge_criterion: str | None = None,
        missing_merge_fallback: str = "separate_bin",
        score_strategy: str = "standard",
        score_weights: dict | None = None,
        normalization_strategy: str = "absolute",
        woe_shrinkage_strength: float = 25.0,
        objective_kwargs: dict | None = None,
        strategy_kwargs: dict | None = None,
    ):
        if max_n_bins is not None:
            max_bins = max_n_bins
        min_n_bins = self._validate_min_n_bins(min_n_bins)
        sample_size = self._validate_sample_size(sample_size)
        if monotonic is not None and monotonic_trend is not None and monotonic != monotonic_trend:
            raise ValueError(
                "`monotonic` and `monotonic_trend` were both provided with different values. "
                "Pass only one of them or keep them consistent."
            )
        monotonic = monotonic if monotonic is not None else monotonic_trend

        self.strategy = strategy
        self.max_bins = max_bins
        self.max_n_bins = max_bins
        self.min_n_bins = min_n_bins
        self.sample_size = sample_size
        self.min_event_rate_diff = min_event_rate_diff
        self.monotonic = monotonic
        self.monotonic_trend = monotonic
        self.check_stability = check_stability
        self.use_optuna = use_optuna
        self.time_col = time_col
        self.force_categorical = force_categorical or []
        self.force_numeric = force_numeric or []
        self.missing_policy = self._normalize_missing_policy(missing_policy)
        self.missing_merge_criterion = self._normalize_missing_merge_criterion(
            missing_merge_criterion,
            missing_policy=self.missing_policy,
        )
        self.missing_merge_fallback = self._normalize_missing_merge_fallback(missing_merge_fallback)
        self.missing_policy_ = self.missing_policy
        self.effective_missing_policy_ = self.missing_policy
        self.missing_merge_criterion_ = self.missing_merge_criterion
        self.missing_merge_fallback_ = self.missing_merge_fallback
        self.objective_kwargs = objective_kwargs or {}
        score_strategy = resolve_score_strategy(score_strategy=score_strategy)
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
        self.sampling_metadata_ = self._resolve_sampling_plan()

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
            params["score_strategy"] = resolve_score_strategy(score_strategy=params["score_strategy"])
        if "objective_kwargs" in params and "score_strategy" in (params["objective_kwargs"] or {}):
            resolve_score_strategy(
                {"score_strategy": params["objective_kwargs"]["score_strategy"]},
                score_strategy=None,
            )
        if "missing_policy" in params:
            params["missing_policy"] = self._normalize_missing_policy(params["missing_policy"])
        prospective_missing_policy = params.get("missing_policy", self.missing_policy)
        if "missing_merge_criterion" in params:
            params["missing_merge_criterion"] = self._normalize_missing_merge_criterion(
                params["missing_merge_criterion"],
                missing_policy=prospective_missing_policy,
            )
        elif "missing_policy" in params:
            inherited_criterion = (
                self.missing_merge_criterion
                if prospective_missing_policy == _MERGE_MISSING_POLICY
                else None
            )
            params["missing_merge_criterion"] = self._normalize_missing_merge_criterion(
                inherited_criterion,
                missing_policy=prospective_missing_policy,
            )
        if "missing_merge_fallback" in params:
            params["missing_merge_fallback"] = self._normalize_missing_merge_fallback(
                params["missing_merge_fallback"]
            )
        if "min_n_bins" in params:
            params["min_n_bins"] = self._validate_min_n_bins(params["min_n_bins"])
        if "sample_size" in params:
            params["sample_size"] = self._validate_sample_size(params["sample_size"])

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
        self.missing_policy_ = self.missing_policy
        self.effective_missing_policy_ = self.missing_policy
        self.missing_merge_criterion_ = self.missing_merge_criterion
        self.missing_merge_fallback_ = self.missing_merge_fallback
        return result

    # ------------------------------------------------------------------
    @staticmethod
    def _normalize_missing_policy(value: str | None) -> str:
        policy = _STANDARD_MISSING_POLICY if value is None else str(value)
        if policy == _LEGACY_POLICY_ALIAS:
            return _STANDARD_MISSING_POLICY
        if policy not in _VALID_MISSING_POLICIES:
            allowed = ", ".join(f"'{item}'" for item in sorted(_VALID_MISSING_POLICIES))
            raise ValueError(
                f"Unsupported missing_policy '{policy}'. Use one of: {allowed}."
            )
        return policy

    # ------------------------------------------------------------------
    @staticmethod
    def _normalize_missing_merge_criterion(
        value: str | None,
        *,
        missing_policy: str,
    ) -> str | None:
        if value is None:
            if missing_policy == _MERGE_MISSING_POLICY:
                raise ValueError(
                    "`missing_merge_criterion` is required when missing_policy='merge'. "
                    "Use 'nearest_event_rate' or 'nearest_woe'."
                )
            return None
        criterion = str(value)
        if missing_policy != _MERGE_MISSING_POLICY:
            raise ValueError(
                "`missing_merge_criterion` can only be used with missing_policy='merge'."
            )
        if criterion not in _VALID_MISSING_MERGE_CRITERIA:
            allowed = ", ".join(f"'{item}'" for item in sorted(_VALID_MISSING_MERGE_CRITERIA))
            raise ValueError(
                f"Unsupported missing_merge_criterion '{criterion}'. Use one of: {allowed}."
            )
        return criterion

    # ------------------------------------------------------------------
    @staticmethod
    def _normalize_missing_merge_fallback(value: str | None) -> str:
        fallback = _SEPARATE_BIN_MISSING_MERGE_FALLBACK if value is None else str(value)
        if fallback not in _VALID_MISSING_MERGE_FALLBACKS:
            allowed = ", ".join(f"'{item}'" for item in sorted(_VALID_MISSING_MERGE_FALLBACKS))
            raise ValueError(
                f"Unsupported missing_merge_fallback '{fallback}'. Use one of: {allowed}."
            )
        return fallback

    # ------------------------------------------------------------------
    @staticmethod
    def _validate_min_n_bins(value: int | None) -> int | None:
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, Integral):
            raise ValueError("`min_n_bins` must be None or a positive integer.")
        value = int(value)
        if value <= 0:
            raise ValueError("`min_n_bins` must be None or a positive integer.")
        return value

    # ------------------------------------------------------------------
    @staticmethod
    def _validate_sample_size(value: int | float) -> int | float:
        if value is None:
            raise ValueError("`sample_size` must be a positive integer or a float in (0, 1].")
        if isinstance(value, bool):
            raise ValueError("`sample_size` must be a positive integer or a float in (0, 1].")
        if isinstance(value, Integral):
            value = int(value)
            if value <= 0:
                raise ValueError("`sample_size` must be a positive integer or a float in (0, 1].")
            return value
        if isinstance(value, Real):
            value = float(value)
            if value <= 0 or value > 1:
                raise ValueError("`sample_size` must be a positive integer or a float in (0, 1].")
            return value
        raise ValueError("`sample_size` must be a positive integer or a float in (0, 1].")

    # ------------------------------------------------------------------
    def _resolve_sampling_plan(self, population_size: int | None = None) -> dict[str, Any]:
        sample_size = self._validate_sample_size(self.sample_size)
        if population_size is not None:
            population_size = int(population_size)
            if population_size < 0:
                raise ValueError("`population_size` must be non-negative when provided.")

        if isinstance(sample_size, int):
            effective_size = (
                min(sample_size, population_size)
                if population_size is not None
                else sample_size
            )
            effective_fraction = (
                (effective_size / population_size)
                if population_size and population_size > 0
                else (0.0 if population_size == 0 else None)
            )
            return {
                "sample_size_requested": sample_size,
                "sample_size_type": "absolute",
                "population_size": population_size,
                "sample_fraction_effective": effective_fraction,
                "sample_size_effective": effective_size,
            }

        effective_size = (
            min(population_size, math.ceil(population_size * sample_size))
            if population_size is not None
            else None
        )
        return {
            "sample_size_requested": sample_size,
            "sample_size_type": "fraction",
            "population_size": population_size,
            "sample_fraction_effective": sample_size,
            "sample_size_effective": effective_size,
        }

    # ------------------------------------------------------------------
    def _pandas_fit_sampling_metadata(self, n_rows: int) -> dict[str, Any]:
        plan = self._resolve_sampling_plan(population_size=n_rows)
        return {
            "input_backend": "pandas",
            "fit_backend": "pandas_core",
            "fit_mode": "pandas_core",
            "sampling_applied": False,
            "sampling_strategy": "none",
            "n_rows_source": int(n_rows),
            "n_rows_fit": int(n_rows),
            "sample_size_requested": plan["sample_size_requested"],
            "sample_size_type": plan["sample_size_type"],
            "sample_plan_effective_if_sampled": {
                "population_size": plan["population_size"],
                "sample_fraction_effective": plan["sample_fraction_effective"],
                "sample_size_effective": plan["sample_size_effective"],
            },
        }

    # ------------------------------------------------------------------
    def _sampling_random_state(self) -> int:
        seed = self.strategy_kwargs.get("sampling_random_state", self.strategy_kwargs.get("random_state", 42))
        try:
            return int(seed)
        except (TypeError, ValueError):
            return 42

    # ------------------------------------------------------------------
    @staticmethod
    def _spark_functions():
        from pyspark.sql import functions as F

        return F

    # ------------------------------------------------------------------
    @staticmethod
    def _pandas_missing_counts(X: pd.DataFrame, columns: Sequence[str]) -> dict[str, int]:
        if not columns:
            return {}
        counts = X.loc[:, list(columns)].isna().sum()
        return {str(column): int(count) for column, count in counts.items()}

    # ------------------------------------------------------------------
    @staticmethod
    def _format_missing_counts(counts: dict[str, int]) -> str:
        return ", ".join(f"{column}={count}" for column, count in counts.items() if count > 0)

    # ------------------------------------------------------------------
    def _raise_forbidden_missing(
        self,
        counts: dict[str, int],
        *,
        context: str,
        backend: str,
    ) -> None:
        present = {column: count for column, count in counts.items() if count > 0}
        if not present:
            return
        detail = self._format_missing_counts(present)
        raise ValueError(
            f"missing_policy='forbid' detected missing values during {context} "
            f"on backend '{backend}': {detail}. "
            "Clean missing values upstream or use missing_policy='standard' or "
            "missing_policy='separate_bin' when missing values are expected."
        )

    # ------------------------------------------------------------------
    def _check_missing_policy_pandas(
        self,
        X: pd.DataFrame,
        columns: Sequence[str],
        *,
        context: str,
    ) -> None:
        if self.missing_policy != _FORBID_MISSING_POLICY:
            return
        self._raise_forbidden_missing(
            self._pandas_missing_counts(X, columns),
            context=context,
            backend="pandas",
        )

    # ------------------------------------------------------------------
    @staticmethod
    def _spark_column_supports_nan(data_type: Any) -> bool:
        try:
            from pyspark.sql import types as T
        except Exception:  # pragma: no cover - import availability checked by caller
            return False
        return isinstance(data_type, (T.DoubleType, T.FloatType))

    # ------------------------------------------------------------------
    @staticmethod
    def _spark_data_types_by_column(X) -> dict[str, Any]:
        schema = getattr(X, "schema", None)
        fields = getattr(schema, "fields", []) or []
        return {
            str(field.name): getattr(field, "dataType", None)
            for field in fields
            if hasattr(field, "name")
        }

    # ------------------------------------------------------------------
    def _spark_missing_count_expressions(self, X, columns: Sequence[str], F):
        fields = self._spark_data_types_by_column(X)
        expressions = []
        for column in columns:
            missing_condition = self._spark_missing_condition(column, F, data_type=fields.get(str(column)))
            expressions.append(
                F.sum(F.when(missing_condition, F.lit(1)).otherwise(F.lit(0))).alias(str(column))
            )
        return expressions

    # ------------------------------------------------------------------
    def _spark_missing_condition(self, column: str, F, *, data_type: Any | None = None):
        col_expr = F.col(column)
        missing_condition = col_expr.isNull()
        if self._spark_column_supports_nan(data_type):
            missing_condition = missing_condition | F.isnan(col_expr)
        return missing_condition

    # ------------------------------------------------------------------
    def _pyspark_missing_counts(self, X, columns: Sequence[str]) -> dict[str, int]:
        if not columns:
            return {}
        F = self._spark_functions()
        expressions = self._spark_missing_count_expressions(X, columns, F)
        row = X.agg(*expressions).collect()[0]
        return {str(column): int(row[str(column)] or 0) for column in columns}

    # ------------------------------------------------------------------
    def _check_missing_policy_pyspark(
        self,
        X,
        columns: Sequence[str],
        *,
        context: str,
    ) -> None:
        if self.missing_policy == _MERGE_MISSING_POLICY:
            if context == "fit":
                return
            fit_backend = getattr(self, "fit_backend_", None)
            if fit_backend not in {"pandas", "pandas_core"}:
                raise NotImplementedError(
                    "missing_policy='merge' Spark transform is only supported after pandas fit."
                )
            if self.missing_merge_fallback != _RAISE_MISSING_MERGE_FALLBACK:
                return
            merge_map = getattr(self, "missing_merge_map_", {}) or {}
            columns_without_decision = [column for column in columns if str(column) not in merge_map]
            counts = self._pyspark_missing_counts(X, columns_without_decision)
            present = {column: count for column, count in counts.items() if count > 0}
            if not present:
                return
            variable, count = next(iter(present.items()))
            self.missing_transform_fallback_log_ = pd.DataFrame(
                [
                    {
                        "variable": variable,
                        "missing_detected": True,
                        "n_missing_transform": int(count),
                        "action": "missing_transform_fallback_raise",
                        "selected_bin_label": None,
                        "fallback_used": True,
                        "training_decision_used": False,
                        "backend": "pyspark",
                    }
                ]
            )
            raise ValueError(
                "missing_policy='merge' detected missing values during Spark transform "
                f"for feature {variable}, but no merge decision was learned during fit."
            )
        if self.missing_policy != _FORBID_MISSING_POLICY:
            return
        self._raise_forbidden_missing(
            self._pyspark_missing_counts(X, columns),
            context=context,
            backend="pyspark",
        )

    # ------------------------------------------------------------------
    def _normalize_pyspark_fit_inputs(
        self,
        X,
        y: str | None = None,
        *,
        target: str | None = None,
        column: str | None = None,
        columns: Sequence[str] | None = None,
        feature: str | None = None,
        features: Sequence[str] | None = None,
        time_col: str | None = None,
    ) -> tuple[str, list[str], list[str]]:
        available_columns = list(X.columns)
        if isinstance(y, str):
            if target is not None and target != y:
                raise ValueError("Pass the target once: use either `y=` or `target=`.")
            target_name = y
        elif target is not None:
            if not isinstance(target, str):
                raise TypeError("PySpark fit requires `target` to be a column name.")
            target_name = target
        elif y is None:
            raise TypeError("PySpark fit requires `y` or `target` to be a column name.")
        else:
            raise TypeError("PySpark fit requires `y` to be a target column name.")

        if target_name not in available_columns:
            raise KeyError(f"Target column '{target_name}' was not found in the PySpark DataFrame.")
        if time_col is not None and time_col not in available_columns:
            raise KeyError(f"`time_col='{time_col}'` was not found in the PySpark DataFrame.")
        if time_col is not None and time_col == target_name:
            raise ValueError("`time_col` cannot point to the target column.")

        selected_columns = self._resolve_feature_selection(
            column=column,
            columns=columns,
            feature=feature,
            features=features,
        )
        if selected_columns is None:
            feature_columns = [
                col for col in available_columns if col not in {target_name, time_col}
            ]
        else:
            missing = [col for col in selected_columns if col not in available_columns]
            if missing:
                raise KeyError(f"Selected feature(s) not found in the PySpark DataFrame: {missing}.")
            if target_name in selected_columns:
                raise ValueError("Selected feature columns must not include the target column.")
            feature_columns = [col for col in selected_columns if col != time_col]

        if not feature_columns:
            raise ValueError("No feature columns were selected for PySpark fit.")

        collect_columns = self._deduplicate_names(
            feature_columns + ([time_col] if time_col is not None else []) + [target_name]
        )
        return target_name, feature_columns, collect_columns

    # ------------------------------------------------------------------
    def _sample_pyspark_dataframe(self, spark_df, *, population_size: int):
        plan = self._resolve_sampling_plan(population_size=population_size)
        seed = self._sampling_random_state()
        sample_size = self.sample_size

        if isinstance(sample_size, int):
            effective_size = plan["sample_size_effective"]
            if effective_size >= population_size:
                sampled = spark_df
            else:
                fraction = plan["sample_fraction_effective"]
                sampled = spark_df.sample(withReplacement=False, fraction=fraction, seed=seed).limit(effective_size)
        else:
            fraction = plan["sample_fraction_effective"]
            sampled = spark_df.sample(withReplacement=False, fraction=fraction, seed=seed)

        return sampled, plan

    # ------------------------------------------------------------------
    def _sampled_missing_merge_metadata(
        self,
        *,
        source_rows: int,
        fit_rows: int,
        sampling_plan: dict[str, Any],
    ) -> dict[str, Any]:
        merge_map = getattr(self, "missing_merge_map_", {}) or {}
        merge_decision_variables = sorted(str(variable) for variable in merge_map)
        merge_decision_count = len(merge_decision_variables)
        return {
            "merge_decision_learned_on_sample": merge_decision_count > 0,
            "merge_decision_count": merge_decision_count,
            "merge_decision_variables": merge_decision_variables,
            "merge_decision_fit_mode": "sampled_to_pandas",
            "merge_decision_n_rows_source": int(source_rows),
            "merge_decision_n_rows_fit": int(fit_rows),
            "merge_decision_sample_size_requested": sampling_plan.get("sample_size_requested"),
            "merge_decision_sample_size_type": sampling_plan.get("sample_size_type"),
            "merge_decision_sample_fraction_effective": sampling_plan.get("sample_fraction_effective"),
            "sampling_caveat": _PYSPARK_MISSING_MERGE_SAMPLED_FIT_CAVEAT,
        }

    # ------------------------------------------------------------------
    def _annotate_sampled_missing_merge_artifacts(self, merge_metadata: dict[str, Any]) -> None:
        if self.missing_policy != _MERGE_MISSING_POLICY:
            return
        caveat = str(merge_metadata.get("sampling_caveat") or "")
        scalar_metadata = {
            key: value
            for key, value in merge_metadata.items()
            if not isinstance(value, (dict, list, tuple, set))
        }
        for attr_name in (
            "missing_profile_",
            "missing_decision_log_",
            "missing_merge_candidates_",
        ):
            table = getattr(self, attr_name, None)
            if not isinstance(table, pd.DataFrame) or table.empty:
                continue
            annotated = table.copy()
            for key, value in scalar_metadata.items():
                annotated[key] = value
            if "variable" in annotated.columns and "merge_decision_learned_on_sample" in annotated.columns:
                learned_variables = {
                    str(variable)
                    for variable in merge_metadata.get("merge_decision_variables", [])
                }
                annotated["merge_decision_learned_on_sample"] = (
                    annotated["variable"].astype(str).isin(learned_variables)
                )
            if "notes" in annotated.columns and caveat:
                annotated["notes"] = annotated["notes"].map(
                    lambda value: (
                        f"{value} Sampling caveat: {caveat}"
                        if pd.notna(value) and caveat not in str(value)
                        else value
                    )
                )
            setattr(self, attr_name, annotated)

    # ------------------------------------------------------------------
    def _fit_pyspark(
        self,
        X,
        y: str | None = None,
        *,
        target: str | None = None,
        column: str | None = None,
        columns: Sequence[str] | None = None,
        feature: str | None = None,
        features: Sequence[str] | None = None,
        time_col: str | None = None,
        copy: bool = True,
        validate: bool = False,
    ):
        time_col = time_col or self.time_col
        target_name, feature_columns, collect_columns = self._normalize_pyspark_fit_inputs(
            X,
            y,
            target=target,
            column=column,
            columns=columns,
            feature=feature,
            features=features,
            time_col=time_col,
        )
        self._check_missing_policy_pyspark(X, feature_columns, context="fit")
        source_rows = int(X.count())
        selected_spark = X.select(*collect_columns)
        sampled_spark, sampling_plan = self._sample_pyspark_dataframe(
            selected_spark,
            population_size=source_rows,
        )
        sample_pdf = sampled_spark.toPandas()
        fit_rows = int(len(sample_pdf))
        if fit_rows == 0 and source_rows > 0:
            sample_pdf = selected_spark.limit(1).toPandas()
            fit_rows = int(len(sample_pdf))

        self.fit(
            sample_pdf,
            y=target_name,
            columns=feature_columns,
            time_col=time_col,
            copy=copy,
            validate=validate,
        )

        sampling_metadata = {
            **sampling_plan,
            "input_backend": "pyspark",
            "fit_backend": "pandas_core",
            "fit_mode": "sampled_to_pandas",
            "sampling_applied": True,
            "sampling_strategy": "random",
            "stratified": False,
            "sampling_limitation": "Random sampling is used; target stratification is not applied.",
            "n_rows_source": source_rows,
            "n_rows_fit": fit_rows,
            "random_state": self._sampling_random_state(),
        }
        backend_metadata = {
            "input_backend": "pyspark",
            "fit_backend": "pandas_core",
            "fit_mode": "sampled_to_pandas",
            "source_columns": list(X.columns),
            "collected_columns": collect_columns,
            "feature_columns": feature_columns,
            "target_name": target_name,
            "time_col": time_col,
        }
        if self.missing_policy == _MERGE_MISSING_POLICY:
            merge_metadata = self._sampled_missing_merge_metadata(
                source_rows=source_rows,
                fit_rows=fit_rows,
                sampling_plan=sampling_plan,
            )
            sampling_metadata.update(merge_metadata)
            backend_metadata.update(merge_metadata)
            self._annotate_sampled_missing_merge_artifacts(merge_metadata)
        self.input_backend_ = "pyspark"
        self.fit_backend_ = "pandas_core"
        self.backend_metadata_ = backend_metadata
        self.sampling_metadata_ = sampling_metadata
        self.source_profile_ = None
        self.source_missing_counts_ = None
        self.missing_sampling_diagnostics_ = None
        source_profile_status = None
        if validate:
            if self.missing_policy == _MERGE_MISSING_POLICY:
                self.source_missing_counts_ = self._pyspark_missing_counts(X, feature_columns)
            self.source_profile_, source_profile_status = self._try_build_pyspark_source_profile(
                X,
                target_name=target_name,
                feature_columns=feature_columns,
                source_rows=source_rows,
            )
            self._refresh_reference_profile()
            self.fit_validation_report_ = self._build_fit_validation_report(
                source_profile=self.source_profile_,
                source_profile_status=source_profile_status,
            )
            self.validation_report_ = self.fit_validation_report_
        else:
            self._refresh_reference_profile()
            self.fit_validation_report_ = None
            self.validation_report_ = None
            self.validation_settings_ = None

        from .reporting import build_binner_metadata

        self.metadata_ = build_binner_metadata(self, time_col=time_col)
        return self

    # ------------------------------------------------------------------
    def _normalize_pyspark_transform_input(
        self,
        X,
        *,
        column: str | None = None,
        columns: Sequence[str] | None = None,
        feature: str | None = None,
        features: Sequence[str] | None = None,
    ) -> list[str]:
        self._ensure_fitted()
        selected_columns = self._resolve_feature_selection(
            column=column,
            columns=columns,
            feature=feature,
            features=features,
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

        missing = [col for col in selected_columns if col not in list(X.columns)]
        if missing:
            raise KeyError(f"PySpark DataFrame is missing fitted feature(s): {missing}.")
        return list(selected_columns)

    # ------------------------------------------------------------------
    @staticmethod
    def _regular_model_bins(table: pd.DataFrame) -> list[Any]:
        if "Bin" in table.columns:
            labels = table["Bin"]
        elif "bin" in table.columns:
            labels = table["bin"]
        else:
            return []
        label_text = labels.astype(str).str.strip().str.lower()
        mask = ~label_text.isin({"total", "totals", "special", "missing", ""})
        mask &= ~label_text.str.startswith("special")
        mask &= ~label_text.str.startswith("missing")
        return labels.loc[mask].tolist()

    # ------------------------------------------------------------------
    def _missing_merge_spark_label(self, column: str) -> Any:
        merge_map = getattr(self, "missing_merge_map_", {}) or {}
        if str(column) in merge_map:
            return merge_map[str(column)]
        if self.missing_merge_fallback == _SEPARATE_BIN_MISSING_MERGE_FALLBACK:
            return "Missing"
        return "Missing"

    # ------------------------------------------------------------------
    def _numeric_supervised_spark_expression(self, column: str, F, *, data_type: Any | None = None):
        model = self._per_feature_binners[column].models_[column]
        splits = [float(split) for split in getattr(model, "splits", [])]
        labels = self._regular_model_bins(model.binning_table.build())
        if len(labels) != len(splits) + 1:
            labels = self.binning_table(column=column)["bin"].tolist()
        col_expr = F.col(column)
        missing_condition = self._spark_missing_condition(column, F, data_type=data_type)
        missing_label = (
            self._missing_merge_spark_label(column)
            if self.missing_policy == _MERGE_MISSING_POLICY
            else "Missing"
        )
        expr = F.when(missing_condition, F.lit(missing_label))

        for idx, label in enumerate(labels):
            if not splits:
                condition = ~missing_condition
            elif idx == 0:
                condition = col_expr < F.lit(splits[0])
            elif idx == len(labels) - 1:
                condition = col_expr >= F.lit(splits[-1])
            else:
                condition = (col_expr >= F.lit(splits[idx - 1])) & (col_expr < F.lit(splits[idx]))
            expr = expr.when(condition, F.lit(label))
        return expr.otherwise(F.lit(labels[-1] if labels else None))

    # ------------------------------------------------------------------
    def _numeric_unsupervised_spark_expression(self, column: str, F, *, data_type: Any | None = None):
        strategy = self._per_feature_binners[column]
        column_index = list(getattr(strategy._kbd, "feature_names_in_", [column])).index(column)
        edges = [float(edge) for edge in strategy._kbd.bin_edges_[column_index]]
        labels = [float(idx) for idx in range(max(0, len(edges) - 1))]
        col_expr = F.col(column)
        missing_condition = self._spark_missing_condition(column, F, data_type=data_type)
        if self.missing_policy == _MERGE_MISSING_POLICY:
            missing_label = self._missing_merge_spark_label(column)
        elif self.missing_policy == _SEPARATE_BIN_MISSING_POLICY:
            missing_label = "Missing"
        else:
            missing_label = float("nan")
        expr = F.when(missing_condition, F.lit(missing_label))
        for idx, label in enumerate(labels):
            if idx == 0:
                condition = col_expr < F.lit(edges[1])
            elif idx == len(labels) - 1:
                condition = col_expr >= F.lit(edges[idx])
            else:
                condition = (col_expr >= F.lit(edges[idx])) & (col_expr < F.lit(edges[idx + 1]))
            expr = expr.when(condition, F.lit(label))
        return expr.otherwise(F.lit(labels[-1] if labels else float("nan")))

    # ------------------------------------------------------------------
    def _categorical_spark_expression(self, column: str, F):
        strategy = self._per_feature_binners[column]
        mapping = dict(getattr(strategy, "category_mapping_", {}) or {})
        missing_token = getattr(strategy, "missing_token_", "_MISSING_")
        unknown_token = getattr(strategy, "unknown_token_", "_UNKNOWN_")
        default_bin = getattr(strategy, "default_bin_", mapping.get(unknown_token))
        col_expr = F.col(column)
        str_col = col_expr.cast("string")
        if self.missing_policy == _MERGE_MISSING_POLICY:
            expr = F.when(col_expr.isNull(), F.lit(self._missing_merge_spark_label(column)))
        elif self.missing_policy == _SEPARATE_BIN_MISSING_POLICY:
            expr = F.when(col_expr.isNull(), F.lit("Missing"))
        else:
            expr = F.when(col_expr.isNull(), F.lit(mapping.get(missing_token, default_bin)))
        for category, label in sorted(mapping.items(), key=lambda item: str(item[0])):
            if category in {missing_token, unknown_token}:
                continue
            expr = expr.when(str_col == F.lit(str(category)), F.lit(label))
        return expr.otherwise(F.lit(default_bin))

    # ------------------------------------------------------------------
    def _spark_transform_expression(self, column: str, F, *, data_type: Any | None = None):
        strategy = self._per_feature_binners[column]
        if hasattr(strategy, "models_") and column in getattr(strategy, "models_", {}):
            return self._numeric_supervised_spark_expression(column, F, data_type=data_type)
        if hasattr(strategy, "_kbd"):
            return self._numeric_unsupervised_spark_expression(column, F, data_type=data_type)
        if hasattr(strategy, "category_mapping_"):
            return self._categorical_spark_expression(column, F)
        raise TypeError(f"Feature '{column}' uses an unsupported binner for Spark transform.")

    # ------------------------------------------------------------------
    def _transform_pyspark(
        self,
        X,
        *,
        column: str | None = None,
        columns: Sequence[str] | None = None,
        feature: str | None = None,
        features: Sequence[str] | None = None,
        return_woe: bool = False,
        return_type: str = "auto",
        validate: bool = False,
    ):
        if return_woe:
            raise NotImplementedError("PySpark transform currently supports return_woe=False only.")
        if return_type not in {"auto", "dataframe"}:
            raise ValueError("PySpark transform preserves DataFrame output; use return_type='auto' or 'dataframe'.")
        selected_columns = self._normalize_pyspark_transform_input(
            X,
            column=column,
            columns=columns,
            feature=feature,
            features=features,
        )
        self._check_missing_policy_pyspark(X, selected_columns, context="transform")
        F = self._spark_functions()
        fields = self._spark_data_types_by_column(X)
        transformed = X
        for selected_column in selected_columns:
            transformed = transformed.withColumn(
                selected_column,
                self._spark_transform_expression(
                    selected_column,
                    F,
                    data_type=fields.get(str(selected_column)),
                ),
            )
        output = transformed.select(*selected_columns)
        if validate:
            self._validate_transform_pyspark(output, X)
        return output

    # ------------------------------------------------------------------
    def _try_build_pyspark_source_profile(
        self,
        X,
        *,
        target_name: str,
        feature_columns: Sequence[str],
        source_rows: int,
    ) -> tuple[pd.DataFrame | None, str]:
        try:
            profile = self._build_bin_profile_pyspark(
                X,
                target_name=target_name,
                feature_columns=feature_columns,
                n_rows=source_rows,
            )
        except ValueError as exc:
            self.source_profile_error_ = str(exc)
            return None, "skipped_profile_too_large"
        return profile, "computed"

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
    @staticmethod
    def _make_temp_column_name(existing_columns: Sequence[str], base: str) -> str:
        existing = set(existing_columns)
        name = base
        i = 1
        while name in existing:
            name = f"{base}_{i}"
            i += 1
        return name

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
    def _regular_bin_mask(summary: pd.DataFrame) -> pd.Series:
        if summary.empty:
            return pd.Series(dtype=bool, index=summary.index)

        mask = pd.Series(True, index=summary.index)
        if "count" in summary.columns:
            counts = pd.to_numeric(summary["count"], errors="coerce").fillna(0)
            mask &= counts > 0

        if "bin" in summary.columns:
            labels = summary["bin"].astype(str).str.strip().str.lower()
            technical = labels.isin({"", "total", "totals", "special", "special codes", "missing"})
            technical |= labels.str.startswith("missing")
            technical |= labels.str.startswith("special")
            mask &= ~technical
        return mask

    # ------------------------------------------------------------------
    def _fitted_summary_mask(self, summary: pd.DataFrame) -> pd.Series:
        if summary.empty:
            return pd.Series(dtype=bool, index=summary.index)

        mask = pd.Series(True, index=summary.index)
        if "count" in summary.columns:
            counts = pd.to_numeric(summary["count"], errors="coerce").fillna(0)
            mask &= counts > 0
        if "bin" in summary.columns:
            labels_raw = summary["bin"].astype(str)
            labels = labels_raw.str.strip().str.lower()
            technical = labels.isin({"total", "totals", "special", "special codes", ""})
            technical |= labels.str.startswith("special")
            if not self._uses_explicit_missing_bin():
                technical |= labels.isin({"missing"})
                technical |= labels.str.startswith("missing")
            mask &= ~technical
            if "variable" in summary.columns:
                mask &= labels_raw != summary["variable"].astype(str)
        return mask

    # ------------------------------------------------------------------
    def _filter_fitted_summary(self, summary: pd.DataFrame) -> pd.DataFrame:
        return summary.loc[self._fitted_summary_mask(summary)].reset_index(drop=True)

    # ------------------------------------------------------------------
    def _uses_explicit_missing_bin(self) -> bool:
        return self.missing_policy in {
            _SEPARATE_BIN_MISSING_POLICY,
            _MERGE_MISSING_POLICY,
        }

    # ------------------------------------------------------------------
    def _is_missing_merge_enabled(self) -> bool:
        return (
            self.missing_policy == _MERGE_MISSING_POLICY
            and self.missing_merge_criterion in _VALID_MISSING_MERGE_CRITERIA
        )

    # ------------------------------------------------------------------
    def _refine_bins_for_policy(
        self,
        bin_summary: pd.DataFrame,
        *,
        min_er_delta: float,
        trend: str | None = None,
        time_col: str | None = None,
        check_stability: bool = False,
    ) -> pd.DataFrame:
        if not self._uses_explicit_missing_bin():
            return refine_bins(
                bin_summary,
                min_er_delta=min_er_delta,
                trend=trend,
                time_col=time_col,
                check_stability=check_stability,
            )

        label_column = "Bin" if "Bin" in bin_summary.columns else "bin"
        labels = bin_summary[label_column].astype(str).str.strip().str.lower()
        missing_mask = labels.str.startswith("missing")
        if not missing_mask.any():
            return refine_bins(
                bin_summary,
                min_er_delta=min_er_delta,
                trend=trend,
                time_col=time_col,
                check_stability=check_stability,
            )

        parts = []
        regular = bin_summary.loc[~missing_mask].copy()
        if not regular.empty:
            parts.append(
                refine_bins(
                    regular,
                    min_er_delta=min_er_delta,
                    trend=trend,
                    time_col=time_col,
                    check_stability=check_stability,
                )
            )
        missing = bin_summary.loc[missing_mask].copy()
        if not missing.empty:
            parts.append(
                refine_bins(
                    missing,
                    min_er_delta=min_er_delta,
                    trend=None,
                    time_col=None,
                    check_stability=False,
                )
            )
        return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()

    # ------------------------------------------------------------------
    @classmethod
    def _count_regular_bins(cls, summary: pd.DataFrame) -> int:
        return int(cls._regular_bin_mask(summary).sum())

    # ------------------------------------------------------------------
    def _refresh_min_n_bins_metadata(self) -> None:
        if self.min_n_bins is None:
            self.min_n_bins_report_ = pd.DataFrame()
            self.min_n_bins_metadata_ = None
            return

        records = []
        if self.bin_summary is not None and not self.bin_summary.empty:
            groups = self.bin_summary.groupby("variable", sort=False)
        else:
            groups = []

        for variable, group in groups:
            n_regular_bins = self._count_regular_bins(group)
            reached = n_regular_bins >= self.min_n_bins
            status = "ok" if reached else "below_minimum"
            reason = None
            if not reached:
                reason = (
                    f"Final binning produced {n_regular_bins} regular bin(s), "
                    f"below min_n_bins={self.min_n_bins}; no artificial cuts were added."
                )
            records.append(
                {
                    "variable": variable,
                    "min_n_bins": self.min_n_bins,
                    "n_regular_bins": n_regular_bins,
                    "min_n_bins_reached": reached,
                    "min_n_bins_status": status,
                    "min_n_bins_reason": reason,
                }
            )

        report = pd.DataFrame(records)
        self.min_n_bins_report_ = report
        reached_all = bool(report["min_n_bins_reached"].all()) if not report.empty else True
        min_regular_bins = (
            int(report["n_regular_bins"].min())
            if not report.empty and "n_regular_bins" in report.columns
            else 0
        )
        self.min_n_bins_metadata_ = {
            "min_n_bins": self.min_n_bins,
            "n_regular_bins": min_regular_bins,
            "min_n_bins_reached": reached_all,
            "min_n_bins_status": "ok" if reached_all else "below_minimum",
            "min_n_bins_reason": None if reached_all else "At least one fitted variable is below min_n_bins.",
            "variables": records,
        }

    # ------------------------------------------------------------------
    @staticmethod
    def _bin_label_key(value: Any) -> str:
        try:
            if pd.isna(value):
                return "<NA>"
        except Exception:
            return str(value)
        return str(value)

    # ------------------------------------------------------------------
    @staticmethod
    def _bin_flag(label: Any, prefix: str) -> bool:
        try:
            if pd.isna(label):
                return prefix == "missing"
        except Exception:
            return str(label).strip().lower().startswith(prefix)
        return str(label).strip().lower().startswith(prefix)

    # ------------------------------------------------------------------
    def _build_bin_lookup(self, variable: str) -> dict[str, dict[str, Any]]:
        if self.bin_summary is None or self.bin_summary.empty:
            return {}
        summary = self.bin_summary.loc[self.bin_summary["variable"] == variable].copy()
        lookup = {}
        for position, row in summary.reset_index(drop=True).iterrows():
            label = row.get("bin")
            lookup[self._bin_label_key(label)] = {
                "bin_id": row.get("bin_code", position),
                "bin_order": row.get("bin_order", position),
            }
        return lookup

    # ------------------------------------------------------------------
    def _build_fit_profile(self, X: pd.DataFrame, y: pd.Series) -> pd.DataFrame:
        transformed = self.transform(X, return_type="dataframe")
        return self._build_profile_from_transformed(transformed, y)

    # ------------------------------------------------------------------
    def _build_missing_audit_from_fit(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        *,
        backend: str,
    ) -> None:
        feature_columns = list(getattr(self, "feature_names_in_", X.columns))
        counts = self._pandas_missing_counts(X, feature_columns)
        transformed = self.transform(X.loc[:, feature_columns], return_type="dataframe")
        target = pd.to_numeric(pd.Series(y, index=X.index), errors="coerce")
        profile_records = []
        decision_records = []

        for variable in feature_columns:
            n_missing = int(counts.get(str(variable), 0))
            missing_detected = n_missing > 0
            missing_mask = X[variable].isna() if variable in X.columns else pd.Series(False, index=X.index)
            bin_label = None
            is_missing_bin = False
            events_missing = None
            event_rate_missing = None
            if missing_detected:
                missing_bins = transformed.loc[missing_mask, variable]
                unique_labels = list(dict.fromkeys(missing_bins.map(self._bin_label_key).tolist()))
                if unique_labels:
                    bin_label = None if unique_labels[0] == "<NA>" else missing_bins.iloc[0]
                    is_missing_bin = any(self._bin_flag(label, "missing") for label in missing_bins)
                events_missing = float(target.loc[missing_mask].sum(skipna=True))
                event_rate_missing = events_missing / n_missing if n_missing else None
                profile_records.append(
                    {
                        "variable": variable,
                        "policy": self.missing_policy,
                        "effective_policy": self.missing_policy,
                        "n_missing_fit": n_missing,
                        "share_missing_fit": n_missing / len(X) if len(X) else np.nan,
                        "events_missing_fit": events_missing,
                        "event_rate_missing_fit": event_rate_missing,
                        "is_missing_bin": bool(is_missing_bin),
                        "bin_label": bin_label,
                        "backend": backend,
                        "context": "fit",
                    }
                )

            if not missing_detected:
                action = "no_missing_detected"
            elif self.missing_policy == _SEPARATE_BIN_MISSING_POLICY:
                action = "separate_bin_created" if is_missing_bin else "separate_bin_requested"
            elif self.missing_policy == _FORBID_MISSING_POLICY:
                action = "forbidden_missing_detected"
            else:
                action = "standard_behavior_preserved"

            decision_records.append(
                {
                    "variable": variable,
                    "policy_requested": self.missing_policy,
                    "effective_policy": self.missing_policy,
                    "missing_detected": bool(missing_detected),
                    "n_missing_fit": n_missing,
                    "action": action,
                    "training_only": True,
                    "backend": backend,
                    "notes": (
                        "Missing values are transformed to an explicit missing bin."
                        if action == "separate_bin_created"
                        else (
                            "Current standard missing behavior was preserved."
                            if action == "standard_behavior_preserved"
                            else "No missing values were observed during fit."
                        )
                    ),
                }
            )

        self.missing_profile_ = pd.DataFrame(profile_records)
        self.missing_decision_log_ = pd.DataFrame(decision_records)
        self.missing_policy_ = self.missing_policy
        self.effective_missing_policy_ = self.missing_policy

    # ------------------------------------------------------------------
    @staticmethod
    def _row_number(row: pd.Series, field: str, default=np.nan) -> float:
        value = pd.to_numeric(pd.Series([row.get(field)]), errors="coerce").iloc[0]
        return float(value) if pd.notna(value) else default

    # ------------------------------------------------------------------
    def _candidate_row_from_profile(
        self,
        *,
        variable: str,
        missing_row: pd.Series,
        candidate: pd.Series,
        rank: int,
        selected: bool = False,
    ) -> dict[str, Any]:
        missing_event_rate = self._row_number(missing_row, "event_rate")
        candidate_event_rate = self._row_number(candidate, "event_rate")
        distance_event_rate = (
            abs(missing_event_rate - candidate_event_rate)
            if np.isfinite(missing_event_rate) and np.isfinite(candidate_event_rate)
            else np.nan
        )
        missing_woe = self._row_number(missing_row, "woe")
        candidate_woe = self._row_number(candidate, "woe")
        distance_woe = (
            abs(missing_woe - candidate_woe)
            if np.isfinite(missing_woe) and np.isfinite(candidate_woe)
            else np.nan
        )
        criterion = self.missing_merge_criterion
        distance = (
            distance_woe
            if criterion == _NEAREST_WOE_MISSING_MERGE_CRITERION
            else distance_event_rate
        )
        distance_metric = (
            "abs_woe_diff"
            if criterion == _NEAREST_WOE_MISSING_MERGE_CRITERION
            else "abs_event_rate_diff"
        )
        return {
            "variable": variable,
            "criterion": criterion,
            "candidate_rank": rank,
            "candidate_bin_id": candidate.get("bin_id"),
            "candidate_bin_label": candidate.get("bin_label"),
            "candidate_bin_order": candidate.get("bin_order"),
            "candidate_n": self._row_number(candidate, "n", default=0.0),
            "candidate_events": self._row_number(candidate, "events", default=0.0),
            "candidate_non_events": self._row_number(candidate, "non_events", default=0.0),
            "candidate_event_rate": candidate_event_rate,
            "candidate_woe": candidate_woe,
            "missing_n": self._row_number(missing_row, "n", default=0.0),
            "missing_events": self._row_number(missing_row, "events", default=0.0),
            "missing_non_events": self._row_number(missing_row, "non_events", default=0.0),
            "missing_event_rate": missing_event_rate,
            "missing_woe": missing_woe,
            "distance_event_rate": distance_event_rate,
            "distance_woe": distance_woe,
            "distance": distance,
            "distance_metric": distance_metric,
            "selected": bool(selected),
        }

    # ------------------------------------------------------------------
    def _build_missing_merge_audit_from_fit(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        pre_profile: pd.DataFrame,
        *,
        backend: str,
    ) -> None:
        feature_columns = list(getattr(self, "feature_names_in_", X.columns))
        counts = self._pandas_missing_counts(X, feature_columns)
        profile_records = []
        decision_records = []
        candidate_records = []
        merge_map: dict[str, Any] = {}
        merge_metrics: dict[str, dict[str, Any]] = {}

        for variable in feature_columns:
            criterion = self.missing_merge_criterion
            distance_field = (
                "distance_woe"
                if criterion == _NEAREST_WOE_MISSING_MERGE_CRITERION
                else "distance_event_rate"
            )
            distance_metric = (
                "abs_woe_diff"
                if criterion == _NEAREST_WOE_MISSING_MERGE_CRITERION
                else "abs_event_rate_diff"
            )
            variable_profile = pre_profile.loc[pre_profile["variable"] == variable].copy()
            n_missing = int(counts.get(str(variable), 0))
            missing_detected = n_missing > 0
            missing_rows = variable_profile.loc[
                variable_profile.get("is_missing_bin", pd.Series(False, index=variable_profile.index))
                .fillna(False)
                .astype(bool)
            ]

            if missing_detected and not missing_rows.empty:
                missing_row = missing_rows.iloc[0]
                missing_n = self._row_number(missing_row, "n", default=float(n_missing))
                missing_events = self._row_number(missing_row, "events", default=0.0)
                missing_non_events = self._row_number(missing_row, "non_events", default=missing_n - missing_events)
                missing_event_rate = self._row_number(missing_row, "event_rate")
                missing_woe = self._row_number(missing_row, "woe")
                missing_share = self._row_number(missing_row, "share")
                profile_record_index = len(profile_records)
                profile_records.append(
                    {
                        "variable": variable,
                        "policy": self.missing_policy,
                        "effective_policy": self.missing_policy,
                        "n_missing_fit": int(missing_n),
                        "share_missing_fit": missing_share,
                        "events_missing_fit": missing_events,
                        "event_rate_missing_fit": missing_event_rate,
                        "woe_missing_fit": missing_woe if np.isfinite(missing_woe) else None,
                        "is_missing_bin": True,
                        "bin_label": missing_row.get("bin_label", "Missing"),
                        "backend": backend,
                        "context": "fit",
                        "merge_criterion": self.missing_merge_criterion,
                        "merged_into_bin_label": None,
                        "merge_distance": None,
                        "merge_status": None,
                    }
                )
            else:
                missing_row = pd.Series(dtype=object)
                missing_n = float(n_missing)
                missing_events = 0.0
                missing_non_events = 0.0
                missing_event_rate = np.nan
                missing_woe = np.nan
                missing_share = np.nan
                profile_record_index = None

            base_decision = {
                "variable": variable,
                "policy_requested": self.missing_policy,
                "effective_policy": self.missing_policy,
                "merge_criterion": self.missing_merge_criterion,
                "missing_merge_criterion": self.missing_merge_criterion,
                "missing_merge_fallback": self.missing_merge_fallback,
                "missing_detected": bool(missing_detected),
                "n_missing_fit": n_missing,
                "event_rate_missing_fit": missing_event_rate if np.isfinite(missing_event_rate) else None,
                "woe_missing_fit": missing_woe if np.isfinite(missing_woe) else None,
                "missing_woe": missing_woe if np.isfinite(missing_woe) else None,
                "training_only": True,
                "backend": backend,
                "fallback": self.missing_merge_fallback,
                "fallback_used": False,
                "selected_bin_label": None,
                "selected_bin_order": None,
                "selected_bin_event_rate": None,
                "selected_bin_woe": None,
                "distance_metric": distance_metric,
                "distance_value": None,
                "distance": None,
                "distance_event_rate": None,
                "distance_woe": None,
                "tie_break_rule": f"{distance_field} asc, candidate_n desc, bin_order asc, bin_label asc",
                "tie_break_applied": False,
                "tie_detected": False,
                "candidate_count": 0,
                "candidate_bins": [],
                "metrics_before": None,
                "metrics_after": None,
            }

            if not missing_detected:
                decision_records.append(
                    {
                        **base_decision,
                        "action": "no_missing_detected",
                        "status": "no_missing_detected",
                        "reason": "no_missing_detected",
                        "notes": "No missing values were observed during fit; no merge destination was learned.",
                    }
                )
                continue

            if missing_rows.empty:
                reason = "missing_profile_unavailable"
                if self.missing_merge_fallback == _RAISE_MISSING_MERGE_FALLBACK:
                    raise ValueError(
                        f"missing_policy='merge' could not build a missing profile for variable "
                        f"'{variable}'."
                    )
                if profile_record_index is not None:
                    profile_records[profile_record_index]["merge_status"] = "kept_separate"
                decision_records.append(
                    {
                        **base_decision,
                        "action": "missing_kept_separate",
                        "status": "kept_separate",
                        "fallback_used": True,
                        "reason": reason,
                        "notes": (
                            "Missing values were kept as a separate bin because the missing profile was unavailable."
                        ),
                    }
                )
                continue

            if criterion == _NEAREST_WOE_MISSING_MERGE_CRITERION and not np.isfinite(missing_woe):
                reason = "missing_woe_not_finite"
                if self.missing_merge_fallback == _RAISE_MISSING_MERGE_FALLBACK:
                    raise ValueError(
                        f"missing_policy='merge' could not compute nearest_woe for variable "
                        f"'{variable}' because the missing WoE is not finite."
                    )
                if profile_record_index is not None:
                    profile_records[profile_record_index]["merge_status"] = "kept_separate"
                decision_records.append(
                    {
                        **base_decision,
                        "action": "missing_kept_separate",
                        "status": "kept_separate",
                        "fallback_used": True,
                        "reason": reason,
                        "notes": (
                            "Missing values were kept as a separate bin because the missing WoE was unavailable."
                        ),
                    }
                )
                continue

            regular = variable_profile.loc[
                variable_profile.get("is_regular_bin", pd.Series(False, index=variable_profile.index))
                .fillna(False)
                .astype(bool)
            ].copy()
            if regular.empty:
                reason = "no_regular_candidate_bins"
                if self.missing_merge_fallback == _RAISE_MISSING_MERGE_FALLBACK:
                    raise ValueError(
                        f"missing_policy='merge' found missing values for variable '{variable}', "
                        f"but no regular candidate bin is available for {criterion} merge."
                    )
                if profile_record_index is not None:
                    profile_records[profile_record_index]["merge_status"] = "kept_separate"
                decision_records.append(
                    {
                        **base_decision,
                        "action": "missing_kept_separate",
                        "status": "kept_separate",
                        "fallback_used": True,
                        "reason": reason,
                        "notes": (
                            "Missing values were kept as a separate bin because no regular candidate bin was available."
                        ),
                    }
                )
                continue

            candidate_rows = []
            for _, candidate in regular.iterrows():
                record = self._candidate_row_from_profile(
                    variable=variable,
                    missing_row=missing_row,
                    candidate=candidate,
                    rank=0,
                )
                candidate_rows.append((record, candidate))

            candidate_rows = [
                (record, candidate)
                for record, candidate in candidate_rows
                if np.isfinite(float(record[distance_field]))
            ]
            if not candidate_rows:
                reason = (
                    "no_finite_candidate_woe"
                    if criterion == _NEAREST_WOE_MISSING_MERGE_CRITERION
                    else "criterion_not_available"
                )
                if self.missing_merge_fallback == _RAISE_MISSING_MERGE_FALLBACK:
                    raise ValueError(
                        f"missing_policy='merge' could not compute {criterion} candidates "
                        f"for variable '{variable}'."
                    )
                if profile_record_index is not None:
                    profile_records[profile_record_index]["merge_status"] = "kept_separate"
                decision_records.append(
                    {
                        **base_decision,
                        "action": "missing_kept_separate",
                        "status": "kept_separate",
                        "fallback_used": True,
                        "reason": reason,
                        "notes": (
                            "Missing values were kept as a separate bin because candidate distances were unavailable."
                        ),
                    }
                )
                continue

            sorted_candidates = sorted(
                candidate_rows,
                key=lambda item: (
                    float(item[0][distance_field]),
                    -float(item[0]["candidate_n"]),
                    self._row_number(item[1], "bin_order", default=float("inf")),
                    self._bin_label_key(item[1].get("bin_label")),
                ),
            )
            best_distance = float(sorted_candidates[0][0][distance_field])
            tied = [
                item
                for item in sorted_candidates
                if np.isclose(float(item[0][distance_field]), best_distance)
            ]
            selected_record, selected_candidate = sorted_candidates[0]
            selected_label = selected_candidate.get("bin_label")
            selected_order = selected_candidate.get("bin_order")

            candidate_bins_payload = []
            for rank, (record, _candidate) in enumerate(sorted_candidates, start=1):
                ranked_record = {
                    **record,
                    "candidate_rank": rank,
                    "selected": rank == 1,
                }
                candidate_records.append(ranked_record)
                candidate_bins_payload.append(
                    {
                        "candidate_rank": rank,
                        "bin_label": ranked_record["candidate_bin_label"],
                        "bin_order": ranked_record["candidate_bin_order"],
                        "n": ranked_record["candidate_n"],
                        "events": ranked_record["candidate_events"],
                        "event_rate": ranked_record["candidate_event_rate"],
                        "woe": ranked_record["candidate_woe"],
                        "distance": ranked_record[distance_field],
                        "distance_event_rate": ranked_record["distance_event_rate"],
                        "distance_woe": ranked_record["distance_woe"],
                        "distance_metric": ranked_record["distance_metric"],
                        "selected": rank == 1,
                    }
                )

            candidate_n = self._row_number(selected_candidate, "n", default=0.0)
            candidate_events = self._row_number(selected_candidate, "events", default=0.0)
            candidate_non_events = self._row_number(selected_candidate, "non_events", default=0.0)
            selected_event_rate = self._row_number(selected_candidate, "event_rate")
            selected_woe = self._row_number(selected_candidate, "woe")
            post_n = missing_n + candidate_n
            post_events = missing_events + candidate_events
            post_non_events = missing_non_events + candidate_non_events
            post_event_rate = post_events / post_n if post_n else np.nan
            post_share = post_n / len(X) if len(X) else np.nan
            metrics_before = {
                "missing": {
                    "n": missing_n,
                    "events": missing_events,
                    "non_events": missing_non_events,
                    "event_rate": missing_event_rate,
                    "woe": missing_woe if np.isfinite(missing_woe) else None,
                    "share": missing_share,
                },
                "selected_bin": {
                    "n": candidate_n,
                    "events": candidate_events,
                    "non_events": candidate_non_events,
                    "event_rate": self._row_number(selected_candidate, "event_rate"),
                    "woe": selected_woe if np.isfinite(selected_woe) else None,
                    "share": self._row_number(selected_candidate, "share"),
                },
            }
            metrics_after = {
                "merged_bin": {
                    "n": post_n,
                    "events": post_events,
                    "non_events": post_non_events,
                    "event_rate": post_event_rate,
                    "share": post_share,
                }
            }
            merge_map[str(variable)] = selected_label
            merge_metrics[str(variable)] = {
                "selected_bin_label": selected_label,
                "selected_bin_order": selected_order,
                "post_n": post_n,
                "post_events": post_events,
                "post_non_events": post_non_events,
                "post_event_rate": post_event_rate,
                "missing_woe": missing_woe if np.isfinite(missing_woe) else None,
                "selected_bin_woe": selected_woe if np.isfinite(selected_woe) else None,
                "distance_woe": selected_record.get("distance_woe"),
                "distance_event_rate": selected_record.get("distance_event_rate"),
                "distance_metric": distance_metric,
            }
            if profile_record_index is not None:
                profile_records[profile_record_index]["merged_into_bin_label"] = selected_label
                profile_records[profile_record_index]["merge_distance"] = best_distance
                profile_records[profile_record_index]["merge_status"] = "merged"
            decision_records.append(
                {
                    **base_decision,
                    "action": "missing_merged",
                    "status": "merged",
                    "reason": None,
                    "selected_bin_label": selected_label,
                    "selected_bin_order": selected_order,
                    "selected_bin_event_rate": selected_event_rate,
                    "selected_bin_woe": selected_woe if np.isfinite(selected_woe) else None,
                    "distance_value": best_distance,
                    "distance": best_distance,
                    "distance_event_rate": selected_record.get("distance_event_rate"),
                    "distance_woe": selected_record.get("distance_woe"),
                    "tie_break_applied": len(tied) > 1,
                    "tie_detected": len(tied) > 1,
                    "candidate_count": len(sorted_candidates),
                    "candidate_bins": candidate_bins_payload,
                    "metrics_before": metrics_before,
                    "metrics_after": metrics_after,
                    "notes": (
                        f"Missing values were merged into the nearest {criterion} regular bin "
                        "using training data."
                    ),
                }
            )

        self.missing_profile_ = pd.DataFrame(profile_records)
        self.missing_decision_log_ = pd.DataFrame(decision_records)
        self.missing_merge_candidates_ = pd.DataFrame(candidate_records)
        self.missing_merge_map_ = merge_map
        self._missing_merge_metrics_ = merge_metrics
        self.missing_policy_ = self.missing_policy
        self.effective_missing_policy_ = self.missing_policy
        self.missing_merge_criterion_ = self.missing_merge_criterion
        self.missing_merge_fallback_ = self.missing_merge_fallback

    # ------------------------------------------------------------------
    def _profile_row_for_bin(
        self,
        profile: pd.DataFrame | None,
        variable: str,
        bin_label: Any,
    ) -> pd.Series | None:
        if profile is None or profile.empty:
            return None
        required = {"variable", "bin_label"}
        if not required.issubset(profile.columns):
            return None
        variable_mask = profile["variable"].astype(str) == str(variable)
        label_mask = profile["bin_label"].map(self._bin_label_key) == self._bin_label_key(bin_label)
        rows = profile.loc[variable_mask & label_mask]
        if rows.empty:
            return None
        return rows.iloc[0]

    # ------------------------------------------------------------------
    def _apply_profile_metrics_to_summary_row(
        self,
        summary: pd.DataFrame,
        mask: pd.Series,
        profile_row: pd.Series,
    ) -> None:
        column_map = {
            "count": "n",
            "n": "n",
            "event": "events",
            "events": "events",
            "non_event": "non_events",
            "non_events": "non_events",
            "event_rate": "event_rate",
            "Event Rate": "event_rate",
            "share": "share",
            "count_pct": "share",
            "Count (%)": "share",
            "woe": "woe",
            "WoE": "woe",
            "iv_component": "iv_component",
            "IV": "iv_component",
        }
        for summary_column, profile_column in column_map.items():
            if summary_column not in summary.columns or profile_column not in profile_row.index:
                continue
            summary.loc[mask, summary_column] = profile_row[profile_column]

    # ------------------------------------------------------------------
    def _apply_missing_merge_to_bin_summary(self, merged_profile: pd.DataFrame | None = None) -> None:
        merge_map = getattr(self, "missing_merge_map_", {}) or {}
        merge_metrics = getattr(self, "_missing_merge_metrics_", {}) or {}
        if not merge_map or self.bin_summary is None or self.bin_summary.empty:
            return

        summary = self.bin_summary.copy()
        for derived_column in ("share", "woe", "iv_component"):
            if derived_column not in summary.columns:
                summary[derived_column] = np.nan

        remove_mask = pd.Series(False, index=summary.index)
        for variable, selected_label in merge_map.items():
            variable_mask = summary["variable"].astype(str) == str(variable)
            labels = summary["bin"].map(self._bin_label_key)
            selected_mask = variable_mask & (labels == self._bin_label_key(selected_label))
            if merged_profile is not None and not merged_profile.empty:
                for row_index in summary.index[variable_mask]:
                    profile_row = self._profile_row_for_bin(
                        merged_profile,
                        str(variable),
                        summary.at[row_index, "bin"],
                    )
                    if profile_row is not None:
                        self._apply_profile_metrics_to_summary_row(
                            summary,
                            pd.Series(summary.index == row_index, index=summary.index),
                            profile_row,
                        )
            metrics = merge_metrics.get(str(variable), {})
            if selected_mask.any() and metrics:
                summary.loc[selected_mask, "count"] = metrics.get("post_n")
                summary.loc[selected_mask, "event"] = metrics.get("post_events")
                summary.loc[selected_mask, "non_event"] = metrics.get("post_non_events")
                summary.loc[selected_mask, "event_rate"] = metrics.get("post_event_rate")
            label_text = summary["bin"].astype(str).str.strip().str.lower()
            remove_mask |= variable_mask & (label_text == "missing")
            remove_mask |= variable_mask & label_text.str.startswith("missing")

        self.bin_summary = summary.loc[~remove_mask].reset_index(drop=True)

    # ------------------------------------------------------------------
    def _collect_missing_merge_audit_from_child_binners(self) -> bool:
        if not hasattr(self, "_per_feature_binners") or not self._per_feature_binners:
            return False

        feature_columns = list(getattr(self, "feature_names_in_", list(self._per_feature_binners)))
        profile_frames = []
        decision_frames = []
        candidate_frames = []
        merge_map: dict[str, Any] = {}
        merge_metrics: dict[str, dict[str, Any]] = {}

        for variable in feature_columns:
            child = self._per_feature_binners.get(variable)
            if not isinstance(child, Binner) or not child._is_missing_merge_enabled():
                return False
            if not hasattr(child, "missing_decision_log_"):
                return False

            profile = getattr(child, "missing_profile_", pd.DataFrame())
            if isinstance(profile, pd.DataFrame) and not profile.empty:
                profile_frames.append(profile.copy(deep=True))

            decision_log = getattr(child, "missing_decision_log_", pd.DataFrame())
            if isinstance(decision_log, pd.DataFrame) and not decision_log.empty:
                decision_frames.append(decision_log.copy(deep=True))

            candidates = getattr(child, "missing_merge_candidates_", pd.DataFrame())
            if isinstance(candidates, pd.DataFrame) and not candidates.empty:
                candidate_frames.append(candidates.copy(deep=True))

            for key, value in (getattr(child, "missing_merge_map_", {}) or {}).items():
                merge_map[str(key)] = value
            for key, value in (getattr(child, "_missing_merge_metrics_", {}) or {}).items():
                merge_metrics[str(key)] = dict(value) if isinstance(value, dict) else value

        self.missing_profile_ = (
            pd.concat(profile_frames, ignore_index=True) if profile_frames else pd.DataFrame()
        )
        self.missing_decision_log_ = (
            pd.concat(decision_frames, ignore_index=True) if decision_frames else pd.DataFrame()
        )
        self.missing_merge_candidates_ = (
            pd.concat(candidate_frames, ignore_index=True) if candidate_frames else pd.DataFrame()
        )
        self.missing_merge_map_ = merge_map
        self._missing_merge_metrics_ = merge_metrics
        self.missing_policy_ = self.missing_policy
        self.effective_missing_policy_ = self.missing_policy
        self.missing_merge_criterion_ = self.missing_merge_criterion
        self.missing_merge_fallback_ = self.missing_merge_fallback
        return True

    # ------------------------------------------------------------------
    def _transform_pandas_core(
        self,
        X: pd.DataFrame,
        selected_columns: Sequence[str],
        *,
        return_woe: bool = False,
    ) -> pd.DataFrame:
        out = {}
        for col in selected_columns:
            binner = self._per_feature_binners[col]
            sig = inspect.signature(binner.transform)
            kwargs = {"return_woe": return_woe} if "return_woe" in sig.parameters else {}
            transformed = binner.transform(X[[col]], **kwargs)
            out[col] = transformed if isinstance(transformed, pd.Series) else transformed[col]
        return pd.DataFrame(out, index=X.index)

    # ------------------------------------------------------------------
    def _route_missing_merge_pandas(
        self,
        transformed: pd.DataFrame,
        X: pd.DataFrame,
        selected_columns: Sequence[str],
    ) -> pd.DataFrame:
        if self.missing_policy != _MERGE_MISSING_POLICY:
            return transformed

        routed = transformed.copy()
        merge_map = getattr(self, "missing_merge_map_", {}) or {}
        transform_records = []
        for column in selected_columns:
            if column not in X.columns:
                continue
            missing_mask = X[column].isna()
            if not bool(missing_mask.any()):
                continue
            n_missing = int(missing_mask.sum())
            column_key = str(column)
            if column_key in merge_map:
                selected_label = merge_map[column_key]
                routed.loc[missing_mask, column] = selected_label
                transform_records.append(
                    {
                        "variable": column,
                        "missing_detected": True,
                        "n_missing_transform": n_missing,
                        "action": "missing_routed_to_learned_merge",
                        "selected_bin_label": selected_label,
                        "fallback_used": False,
                        "training_decision_used": True,
                    }
                )
                continue
            if self.missing_merge_fallback == _SEPARATE_BIN_MISSING_MERGE_FALLBACK:
                routed.loc[missing_mask, column] = "Missing"
                transform_records.append(
                    {
                        "variable": column,
                        "missing_detected": True,
                        "n_missing_transform": n_missing,
                        "action": "missing_transform_fallback_separate_bin",
                        "selected_bin_label": "Missing",
                        "fallback_used": True,
                        "training_decision_used": False,
                    }
                )
                continue
            transform_records.append(
                {
                    "variable": column,
                    "missing_detected": True,
                    "n_missing_transform": n_missing,
                    "action": "missing_transform_fallback_raise",
                    "selected_bin_label": None,
                    "fallback_used": True,
                    "training_decision_used": False,
                }
            )
            self.missing_transform_fallback_log_ = pd.DataFrame(transform_records)
            raise ValueError(
                f"missing_policy='merge' detected missing values during transform for "
                f"feature '{column}', but no missing merge decision was learned during fit."
            )
        self.missing_transform_fallback_log_ = pd.DataFrame(transform_records)
        return routed

    # ------------------------------------------------------------------
    def _fitted_woe_lookup(self, variable: str) -> dict[str, float]:
        profile = getattr(self, "fit_profile_", None)
        if profile is None or profile.empty or "woe" not in profile.columns:
            return {}
        rows = profile.loc[profile["variable"].astype(str) == str(variable)]
        lookup: dict[str, float] = {}
        for _, row in rows.iterrows():
            woe = pd.to_numeric(pd.Series([row.get("woe")]), errors="coerce").iloc[0]
            if np.isfinite(float(woe)):
                lookup[self._bin_label_key(row.get("bin_label"))] = float(woe)
        return lookup

    # ------------------------------------------------------------------
    def _map_missing_merge_labels_to_woe(
        self,
        transformed: pd.DataFrame,
        selected_columns: Sequence[str],
    ) -> pd.DataFrame:
        mapped = transformed.copy()
        merge_map = getattr(self, "missing_merge_map_", {}) or {}
        for column in selected_columns:
            if column not in mapped.columns:
                continue
            labels = mapped[column]
            label_keys = labels.map(self._bin_label_key)
            if label_keys.map(lambda value: self._bin_flag(value, "missing")).any() and str(column) not in merge_map:
                raise ValueError(
                    f"missing_policy='merge' cannot return WoE for missing values in feature "
                    f"'{column}' because no missing merge decision was learned during fit and "
                    "fallback 'separate_bin' has no fitted WoE."
                )
            woe_lookup = self._fitted_woe_lookup(str(column))
            if not woe_lookup:
                raise ValueError(
                    f"missing_policy='merge' cannot return WoE for feature '{column}' because no fitted "
                    "WoE lookup is available."
                )
            unknown = sorted({key for key in label_keys if key not in woe_lookup})
            if unknown:
                formatted = ", ".join(map(str, unknown[:5]))
                raise ValueError(
                    f"missing_policy='merge' cannot return WoE for feature '{column}' because fitted "
                    f"WoE is unavailable for transformed bin label(s): {formatted}."
                )
            mapped[column] = label_keys.map(woe_lookup).astype(float)
        return mapped

    # ------------------------------------------------------------------
    def _missing_merge_destination_woe(self, variable: str, selected_label: Any) -> float:
        woe_lookup = self._fitted_woe_lookup(variable)
        selected_key = self._bin_label_key(selected_label)
        if selected_key not in woe_lookup:
            raise ValueError(
                f"missing_policy='merge' cannot return WoE for missing values in feature "
                f"'{variable}' because the learned destination bin has no fitted WoE."
            )
        return woe_lookup[selected_key]

    # ------------------------------------------------------------------
    def _finalize_fit_missing_audit(
        self,
        X_features: pd.DataFrame,
        y: pd.Series,
        *,
        backend: str,
    ) -> None:
        if self._is_missing_merge_enabled():
            if not self._collect_missing_merge_audit_from_child_binners():
                pre_transformed = self._transform_pandas_core(
                    X_features,
                    list(getattr(self, "feature_names_in_", X_features.columns)),
                )
                pre_profile = self._build_profile_from_transformed(pre_transformed, y)
                self._build_missing_merge_audit_from_fit(
                    X_features,
                    y,
                    pre_profile,
                    backend=backend,
                )
            merged_fit_profile = self._build_fit_profile(X_features, y)
            self._apply_missing_merge_to_bin_summary(merged_profile=merged_fit_profile)
            self._compute_iv_metrics()
            self._refresh_min_n_bins_metadata()
            self.fit_profile_ = merged_fit_profile
            return

        self.fit_profile_ = self._build_fit_profile(X_features, y)
        self._build_missing_audit_from_fit(X_features, y, backend=backend)

    # ------------------------------------------------------------------
    @staticmethod
    def _missing_summary_from_profile(profile: pd.DataFrame | None) -> dict[str, Any]:
        if profile is None or profile.empty or "is_missing_bin" not in profile.columns:
            return {
                "variables_with_missing_bins": 0,
                "missing_profile_rows": 0,
                "missing_rows": 0,
            }
        missing_rows = profile.loc[profile["is_missing_bin"].fillna(False).astype(bool)]
        if missing_rows.empty:
            return {
                "variables_with_missing_bins": 0,
                "missing_profile_rows": 0,
                "missing_rows": 0,
            }
        n_values = pd.to_numeric(missing_rows.get("n", pd.Series(dtype=float)), errors="coerce").fillna(0)
        return {
            "variables_with_missing_bins": int(missing_rows["variable"].nunique(dropna=False)),
            "missing_profile_rows": int(len(missing_rows)),
            "missing_rows": int(n_values.sum()),
        }

    # ------------------------------------------------------------------
    def _build_profile_from_transformed(self, transformed: pd.DataFrame, y: pd.Series) -> pd.DataFrame:
        target = pd.to_numeric(pd.Series(y, index=transformed.index), errors="coerce")
        total_rows = len(transformed)
        total_events = float(target.sum(skipna=True))
        total_non_events = float(total_rows - total_events)
        records = []

        for variable in transformed.columns:
            lookup = self._build_bin_lookup(variable)
            df = pd.DataFrame(
                {
                    "bin_label": transformed[variable],
                    "target": target,
                },
                index=transformed.index,
            )
            grouped = df.groupby("bin_label", sort=False, dropna=False)["target"]
            group_count = int(grouped.ngroups)
            smoothed_total_events = total_events + 0.5 * group_count
            smoothed_total_non_events = total_non_events + 0.5 * group_count

            for fallback_order, (bin_label, group) in enumerate(grouped):
                n = int(group.size)
                events = float(group.sum(skipna=True))
                non_events = float(n - events)
                event_rate = events / n if n else np.nan
                std_error = (
                    math.sqrt(event_rate * (1.0 - event_rate) / n)
                    if n and np.isfinite(event_rate)
                    else np.nan
                )
                ci_lower = max(0.0, event_rate - 1.96 * std_error) if np.isfinite(std_error) else np.nan
                ci_upper = min(1.0, event_rate + 1.96 * std_error) if np.isfinite(std_error) else np.nan
                event_dist = (events + 0.5) / smoothed_total_events if smoothed_total_events else np.nan
                non_event_dist = (
                    (non_events + 0.5) / smoothed_total_non_events
                    if smoothed_total_non_events
                    else np.nan
                )
                woe = (
                    math.log(non_event_dist / event_dist)
                    if event_dist and non_event_dist and np.isfinite(event_dist) and np.isfinite(non_event_dist)
                    else np.nan
                )
                iv_component = (
                    (non_event_dist - event_dist) * woe
                    if np.isfinite(woe) and np.isfinite(non_event_dist) and np.isfinite(event_dist)
                    else np.nan
                )
                lookup_entry = lookup.get(self._bin_label_key(bin_label), {})
                is_missing = self._bin_flag(bin_label, "missing")
                is_special = self._bin_flag(bin_label, "special")
                records.append(
                    {
                        "variable": variable,
                        "bin_id": lookup_entry.get("bin_id"),
                        "bin_label": None if self._bin_label_key(bin_label) == "<NA>" else bin_label,
                        "bin_order": lookup_entry.get("bin_order", len(lookup) + fallback_order),
                        "n": n,
                        "events": events,
                        "non_events": non_events,
                        "event_rate": event_rate,
                        "event_rate_std_error": std_error,
                        "event_rate_ci_lower": ci_lower,
                        "event_rate_ci_upper": ci_upper,
                        "share": n / total_rows if total_rows else np.nan,
                        "woe": woe,
                        "iv_component": iv_component,
                        "is_missing_bin": is_missing,
                        "is_special_bin": is_special,
                        "is_regular_bin": bool(n > 0 and not is_missing and not is_special),
                    }
                )

        profile = pd.DataFrame(records)
        if not profile.empty:
            profile = profile.sort_values(["variable", "bin_order"], kind="mergesort").reset_index(drop=True)
        return profile

    # ------------------------------------------------------------------
    @staticmethod
    def _profile_n_rows(profile: pd.DataFrame | None) -> int:
        if profile is None or profile.empty or "n" not in profile.columns:
            return 0
        n_values = pd.to_numeric(profile["n"], errors="coerce").fillna(0)
        if "variable" in profile.columns:
            rows_by_variable = n_values.groupby(profile["variable"], sort=False).sum()
            return int(rows_by_variable.max()) if not rows_by_variable.empty else 0
        return int(n_values.sum())

    # ------------------------------------------------------------------
    @staticmethod
    def _profile_variable_count(profile: pd.DataFrame | None) -> int:
        if profile is None or profile.empty or "variable" not in profile.columns:
            return 0
        return int(profile["variable"].nunique(dropna=False))

    # ------------------------------------------------------------------
    @staticmethod
    def _metadata_int(mapping: dict[str, Any] | None, key: str) -> int | None:
        if not isinstance(mapping, dict) or mapping.get(key) is None:
            return None
        try:
            return int(mapping[key])
        except (TypeError, ValueError):
            return None

    # ------------------------------------------------------------------
    def _build_profile_from_aggregates(
        self,
        aggregate_profile: pd.DataFrame,
        *,
        n_rows_by_variable: dict[str, int] | None = None,
    ) -> pd.DataFrame:
        if aggregate_profile is None or aggregate_profile.empty:
            return pd.DataFrame()

        aggregates = aggregate_profile.copy()
        aggregates["n"] = pd.to_numeric(aggregates["n"], errors="coerce").fillna(0).astype(int)
        aggregates["events"] = pd.to_numeric(aggregates["events"], errors="coerce").fillna(0.0)
        n_rows_by_variable = n_rows_by_variable or {}
        records = []

        for variable, group in aggregates.groupby("variable", sort=False, dropna=False):
            lookup = self._build_bin_lookup(variable)
            total_rows = n_rows_by_variable.get(variable)
            if total_rows is None:
                total_rows = int(group["n"].sum())
            total_events = float(group["events"].sum(skipna=True))
            total_non_events = float(total_rows - total_events)
            group_count = int(len(group))
            smoothed_total_events = total_events + 0.5 * group_count
            smoothed_total_non_events = total_non_events + 0.5 * group_count

            for fallback_order, row in enumerate(group.itertuples(index=False)):
                bin_label = row.bin_label
                n = int(row.n)
                events = float(row.events or 0.0)
                non_events = float(n - events)
                event_rate = events / n if n else np.nan
                std_error = (
                    math.sqrt(event_rate * (1.0 - event_rate) / n)
                    if n and np.isfinite(event_rate)
                    else np.nan
                )
                ci_lower = max(0.0, event_rate - 1.96 * std_error) if np.isfinite(std_error) else np.nan
                ci_upper = min(1.0, event_rate + 1.96 * std_error) if np.isfinite(std_error) else np.nan
                event_dist = (events + 0.5) / smoothed_total_events if smoothed_total_events else np.nan
                non_event_dist = (
                    (non_events + 0.5) / smoothed_total_non_events
                    if smoothed_total_non_events
                    else np.nan
                )
                woe = (
                    math.log(non_event_dist / event_dist)
                    if event_dist and non_event_dist and np.isfinite(event_dist) and np.isfinite(non_event_dist)
                    else np.nan
                )
                iv_component = (
                    (non_event_dist - event_dist) * woe
                    if np.isfinite(woe) and np.isfinite(non_event_dist) and np.isfinite(event_dist)
                    else np.nan
                )
                lookup_entry = lookup.get(self._bin_label_key(bin_label), {})
                is_missing = self._bin_flag(bin_label, "missing")
                is_special = self._bin_flag(bin_label, "special")
                records.append(
                    {
                        "variable": variable,
                        "bin_id": lookup_entry.get("bin_id"),
                        "bin_label": None if self._bin_label_key(bin_label) == "<NA>" else bin_label,
                        "bin_order": lookup_entry.get("bin_order", len(lookup) + fallback_order),
                        "n": n,
                        "events": events,
                        "non_events": non_events,
                        "event_rate": event_rate,
                        "event_rate_std_error": std_error,
                        "event_rate_ci_lower": ci_lower,
                        "event_rate_ci_upper": ci_upper,
                        "share": n / total_rows if total_rows else np.nan,
                        "woe": woe,
                        "iv_component": iv_component,
                        "is_missing_bin": is_missing,
                        "is_special_bin": is_special,
                        "is_regular_bin": bool(n > 0 and not is_missing and not is_special),
                    }
                )

        profile = pd.DataFrame(records)
        if not profile.empty:
            profile = profile.sort_values(["variable", "bin_order"], kind="mergesort").reset_index(drop=True)
        return profile

    # ------------------------------------------------------------------
    def _collect_pyspark_profile_aggregate(self, profile_sdf, *, remaining_rows: int) -> tuple[pd.DataFrame, int]:
        if remaining_rows <= 0:
            raise ValueError("Spark profile aggregation produced more rows than the configured collection guard.")
        # This collection is only for an already aggregated variable/bin profile.
        profile_rows = int(profile_sdf.limit(remaining_rows + 1).count())
        if profile_rows > remaining_rows:
            raise ValueError("Spark profile aggregation produced more rows than the configured collection guard.")
        return profile_sdf.toPandas(), profile_rows

    # ------------------------------------------------------------------
    def _build_bin_profile_pyspark(
        self,
        X,
        *,
        target_name: str,
        feature_columns: Sequence[str],
        n_rows: int | None = None,
    ) -> pd.DataFrame:
        F = self._spark_functions()
        settings = self._default_validation_settings()
        max_profile_rows = int(settings.get("max_profile_rows_to_collect", _MAX_PROFILE_ROWS_TO_COLLECT))
        existing_columns = list(X.columns)
        fields = self._spark_data_types_by_column(X)
        bin_col = self._make_temp_column_name(existing_columns, "__riskbands_bin_label")
        target_col = self._make_temp_column_name(
            [*existing_columns, bin_col],
            "__riskbands_target",
        )
        profile_parts = []
        collected_rows = 0
        n_rows_by_variable = {
            str(variable): int(n_rows)
            for variable in feature_columns
            if n_rows is not None
        }

        for variable in feature_columns:
            profile_sdf = (
                X.withColumn(
                    bin_col,
                    self._spark_transform_expression(
                        variable,
                        F,
                        data_type=fields.get(str(variable)),
                    ),
                )
                .withColumn(target_col, F.col(target_name).cast("double"))
                .groupBy(bin_col)
                .agg(
                    F.count(F.lit(1)).alias("n"),
                    F.sum(F.coalesce(F.col(target_col), F.lit(0.0))).alias("events"),
                )
                .withColumn("variable", F.lit(variable))
                .withColumn("bin_label", F.col(bin_col))
                .select("variable", "bin_label", "n", "events")
            )
            part, part_rows = self._collect_pyspark_profile_aggregate(
                profile_sdf,
                remaining_rows=max_profile_rows - collected_rows,
            )
            collected_rows += part_rows
            profile_parts.append(part)

        if not profile_parts:
            return pd.DataFrame()
        aggregate_profile = pd.concat(profile_parts, ignore_index=True)
        return self._build_profile_from_aggregates(
            aggregate_profile,
            n_rows_by_variable=n_rows_by_variable,
        )

    # ------------------------------------------------------------------
    def _default_validation_settings(self) -> dict[str, Any]:
        return {
            "min_bin_n": 30,
            "min_bin_events": 5,
            "max_event_rate_std_error": 0.10,
            "min_event_rate_abs_delta": 0.05,
            "max_sample_event_rate_abs_diff": 0.10,
            "max_sample_share_abs_diff": 0.10,
            "warning_z_score": 2.0,
            "critical_z_score": 3.0,
            "critical_event_rate_abs_delta": 0.20,
            "min_fit_rows": 100,
            "max_profile_rows_to_collect": _MAX_PROFILE_ROWS_TO_COLLECT,
        }

    # ------------------------------------------------------------------
    def _compare_profiles(
        self,
        left: pd.DataFrame,
        right: pd.DataFrame,
        *,
        left_name: str,
        right_name: str,
    ) -> pd.DataFrame:
        if left is None or right is None or left.empty or right.empty:
            return pd.DataFrame()
        left_cmp = left.copy()
        right_cmp = right.copy()
        left_cmp["bin_label_key"] = left_cmp["bin_label"].map(self._bin_label_key)
        right_cmp["bin_label_key"] = right_cmp["bin_label"].map(self._bin_label_key)
        merged = left_cmp.merge(
            right_cmp,
            on=["variable", "bin_label_key"],
            how="outer",
            suffixes=(f"_{left_name}", f"_{right_name}"),
        )
        merged["event_rate_abs_diff"] = (
            pd.to_numeric(merged[f"event_rate_{left_name}"], errors="coerce")
            - pd.to_numeric(merged[f"event_rate_{right_name}"], errors="coerce")
        ).abs()
        merged["share_abs_diff"] = (
            pd.to_numeric(merged[f"share_{left_name}"], errors="coerce")
            - pd.to_numeric(merged[f"share_{right_name}"], errors="coerce")
        ).abs()
        return merged

    # ------------------------------------------------------------------
    @staticmethod
    def _json_number_or_none(value: Any) -> float | None:
        number = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
        if pd.isna(number) or not np.isfinite(float(number)):
            return None
        return float(number)

    # ------------------------------------------------------------------
    @staticmethod
    def _json_int_or_none(value: Any) -> int | None:
        number = Binner._json_number_or_none(value)
        return int(number) if number is not None else None

    # ------------------------------------------------------------------
    @staticmethod
    def _json_label_or_none(value: Any) -> Any:
        try:
            if pd.isna(value):
                return None
        except (TypeError, ValueError):
            return value
        return value

    # ------------------------------------------------------------------
    def _profile_comparison_records(
        self,
        comparison: pd.DataFrame,
        *,
        left_name: str,
        right_name: str,
    ) -> list[dict[str, Any]]:
        if comparison is None or comparison.empty:
            return []

        records = []
        for _, row in comparison.iterrows():
            left_label = row.get(f"bin_label_{left_name}")
            right_label = row.get(f"bin_label_{right_name}")
            bin_label = left_label
            if self._json_label_or_none(bin_label) is None:
                bin_label = right_label
            n_left = self._json_int_or_none(row.get(f"n_{left_name}"))
            n_right = self._json_int_or_none(row.get(f"n_{right_name}"))
            records.append(
                {
                    "variable": row.get("variable"),
                    "bin_label": self._json_label_or_none(bin_label),
                    f"present_in_{left_name}": n_left is not None,
                    f"present_in_{right_name}": n_right is not None,
                    f"n_{left_name}": n_left,
                    f"n_{right_name}": n_right,
                    f"event_rate_{left_name}": self._json_number_or_none(row.get(f"event_rate_{left_name}")),
                    f"event_rate_{right_name}": self._json_number_or_none(row.get(f"event_rate_{right_name}")),
                    f"share_{left_name}": self._json_number_or_none(row.get(f"share_{left_name}")),
                    f"share_{right_name}": self._json_number_or_none(row.get(f"share_{right_name}")),
                    "event_rate_abs_diff": self._json_number_or_none(row.get("event_rate_abs_diff")),
                    "share_abs_diff": self._json_number_or_none(row.get("share_abs_diff")),
                }
            )
        return records

    # ------------------------------------------------------------------
    @staticmethod
    def _rows_by_variable(table: pd.DataFrame | None) -> dict[str, pd.Series]:
        if table is None or table.empty or "variable" not in table.columns:
            return {}
        rows = {}
        for _, row in table.iterrows():
            rows.setdefault(str(row.get("variable")), row)
        return rows

    # ------------------------------------------------------------------
    def _build_missing_sampling_diagnostics(
        self,
        *,
        fit_rows: int | None,
        source_rows: int | None,
    ) -> list[dict[str, Any]]:
        if self.missing_policy != _MERGE_MISSING_POLICY:
            return []

        source_counts = getattr(self, "source_missing_counts_", None)
        if not isinstance(source_counts, dict):
            return []

        decision_rows = self._rows_by_variable(getattr(self, "missing_decision_log_", None))
        profile_rows = self._rows_by_variable(getattr(self, "missing_profile_", None))
        merge_map = getattr(self, "missing_merge_map_", {}) or {}
        learned_variables = {str(variable) for variable in merge_map}
        variables = list(getattr(self, "feature_names_in_", []) or [])
        for variable in [*source_counts, *decision_rows, *profile_rows, *merge_map]:
            if str(variable) not in {str(existing) for existing in variables}:
                variables.append(str(variable))

        settings = self._default_validation_settings()
        diagnostics = []
        for variable in variables:
            variable_key = str(variable)
            decision = decision_rows.get(variable_key, pd.Series(dtype=object))
            profile = profile_rows.get(variable_key, pd.Series(dtype=object))
            sample_count = self._json_int_or_none(decision.get("n_missing_fit"))
            if sample_count is None:
                sample_count = self._json_int_or_none(profile.get("n_missing_fit")) or 0
            source_count = int(source_counts.get(variable_key, 0) or 0)
            sample_share = self._json_number_or_none(profile.get("share_missing_fit"))
            if sample_share is None and fit_rows:
                sample_share = sample_count / int(fit_rows)
            source_share = source_count / int(source_rows) if source_rows else None
            share_diff = (
                abs(sample_share - source_share)
                if sample_share is not None and source_share is not None
                else None
            )

            destination = self._json_label_or_none(decision.get("selected_bin_label"))
            if destination is None:
                destination = self._json_label_or_none(profile.get("merged_into_bin_label"))
            learned = variable_key in learned_variables
            if "merge_decision_learned_on_sample" in decision.index:
                learned = bool(decision.get("merge_decision_learned_on_sample"))

            alert_flags = []
            if source_count > 0 and sample_count == 0:
                alert_flags.append("source_missing_not_seen_in_sample")
            if source_count > 0 and not learned:
                alert_flags.append("merge_decision_not_learned_but_source_has_missing")
            if share_diff is not None and share_diff >= settings["max_sample_share_abs_diff"]:
                alert_flags.append("sample_share_shift")

            diagnostics.append(
                {
                    "variable": variable_key,
                    "missing_share_sample_fit": sample_share,
                    "missing_share_source_spark": source_share,
                    "missing_share_abs_diff": share_diff,
                    "missing_count_sample_fit": int(sample_count),
                    "missing_count_source_spark": int(source_count),
                    "missing_merge_destination_learned": destination,
                    "merge_decision_learned_on_sample": learned,
                    "fallback_risk": bool(source_count > 0 and not learned),
                    "status": "warning" if alert_flags else "ok",
                    "alert_flags": alert_flags,
                }
            )
        return diagnostics

    # ------------------------------------------------------------------
    @staticmethod
    def _missing_sampling_summary(diagnostics: list[dict[str, Any]]) -> dict[str, Any]:
        if not diagnostics:
            return {
                "status": "not_available",
                "n_variables": 0,
                "n_warnings": 0,
                "max_missing_share_abs_diff": None,
            }
        max_diff = max(
            (
                float(row["missing_share_abs_diff"])
                for row in diagnostics
                if row.get("missing_share_abs_diff") is not None
            ),
            default=None,
        )
        warning_rows = [row for row in diagnostics if row.get("status") != "ok"]
        return {
            "status": "warning" if warning_rows else "ok",
            "n_variables": int(len(diagnostics)),
            "n_warnings": int(len(warning_rows)),
            "variables_with_source_missing_not_seen_in_sample": [
                row["variable"]
                for row in diagnostics
                if "source_missing_not_seen_in_sample" in row.get("alert_flags", [])
            ],
            "variables_with_unlearned_source_missing": [
                row["variable"]
                for row in diagnostics
                if "merge_decision_not_learned_but_source_has_missing" in row.get("alert_flags", [])
            ],
            "max_missing_share_abs_diff": max_diff,
        }

    # ------------------------------------------------------------------
    def _event_rate_profile_alerts(
        self,
        application_profile: pd.DataFrame,
        reference_profile: pd.DataFrame,
        *,
        application_name: str = "application",
        reference_name: str = "reference",
    ) -> list[dict[str, Any]]:
        settings = self._default_validation_settings()
        comparison = self._compare_profiles(
            application_profile,
            reference_profile,
            left_name=application_name,
            right_name=reference_name,
        )
        alerts = []

        def number(row, field: str, suffix: str, default=np.nan) -> float:
            value = pd.to_numeric(pd.Series([row.get(f"{field}_{suffix}")]), errors="coerce").iloc[0]
            return float(value) if pd.notna(value) else default

        for _, row in comparison.iterrows():
            n_app = number(row, "n", application_name, default=0.0)
            n_ref = number(row, "n", reference_name, default=0.0)
            events_app = number(row, "events", application_name, default=0.0)
            events_ref = number(row, "events", reference_name, default=0.0)
            er_app = number(row, "event_rate", application_name)
            er_ref = number(row, "event_rate", reference_name)
            se_app = number(row, "event_rate_std_error", application_name)
            se_ref = number(row, "event_rate_std_error", reference_name)
            delta = abs(er_app - er_ref) if np.isfinite(er_app) and np.isfinite(er_ref) else np.nan
            pooled_se = math.sqrt(
                (se_app if np.isfinite(se_app) else 0.0) ** 2
                + (se_ref if np.isfinite(se_ref) else 0.0) ** 2
            )
            z_score = delta / pooled_se if pooled_se and np.isfinite(delta) else np.nan

            status = "ok"
            flags = []
            message = "Event rate within expected uncertainty."
            recommendation = None
            if n_ref < settings["min_bin_n"]:
                status = "insufficient_reference_sample"
                flags.append("insufficient_reference_sample")
                message = "Reference bin has too few records to interpret event-rate movement robustly."
                recommendation = "Consider increasing sample_size or using a larger reference sample."
            elif events_ref < settings["min_bin_events"]:
                status = "insufficient_events"
                flags.append("insufficient_events")
                message = "Reference bin has too few events to support a stable event-rate comparison."
                recommendation = "Consider increasing sample_size when the reference comes from training sampling."
            elif n_app < settings["min_bin_n"] or events_app < settings["min_bin_events"]:
                status = "insufficient_application_sample"
                flags.append("insufficient_application_sample")
                message = "Application bin is too small or has too few events for a stable comparison."
                recommendation = "Application base is small for this bin; interpret drift cautiously."
            elif np.isfinite(delta) and delta >= settings["min_event_rate_abs_delta"]:
                if (
                    np.isfinite(z_score)
                    and z_score >= settings["critical_z_score"]
                    or delta >= settings["critical_event_rate_abs_delta"]
                ):
                    status = "critical"
                    flags.extend(["critical_event_rate_shift", "possible_population_drift"])
                    message = "Possible population drift: large event-rate shift beyond expected uncertainty."
                elif np.isfinite(z_score) and z_score >= settings["warning_z_score"]:
                    status = "warning"
                    flags.extend(["event_rate_shift", "possible_population_drift"])
                    message = "Possible population drift: event-rate shift is larger than expected uncertainty."

            alerts.append(
                {
                    "variable": row.get("variable"),
                    "bin_label": row.get(f"bin_label_{application_name}", row.get(f"bin_label_{reference_name}")),
                    "status": status,
                    "alert_flags": flags,
                    "event_rate_application": er_app,
                    "event_rate_reference": er_ref,
                    "event_rate_abs_diff": delta,
                    "z_score": z_score if np.isfinite(z_score) else None,
                    "n_application": n_app,
                    "n_reference": n_ref,
                    "events_application": events_app,
                    "events_reference": events_ref,
                    "message": message,
                    "recommendation": recommendation,
                }
            )
        return alerts

    # ------------------------------------------------------------------
    def _build_fit_validation_report(
        self,
        *,
        source_profile: pd.DataFrame | None = None,
        source_profile_status: str | None = None,
    ) -> dict[str, Any]:
        settings = self._default_validation_settings()
        self.validation_settings_ = settings
        profile = getattr(self, "fit_profile_", pd.DataFrame())
        if profile is None:
            profile = pd.DataFrame()
        missing_summary = self._missing_summary_from_profile(profile)

        bin_alerts = []
        variable_status = []
        if not profile.empty:
            for variable, group in profile.groupby("variable", sort=False):
                variable_alert_count = 0
                for _, row in group.iterrows():
                    flags = []
                    n = float(row.get("n", 0) or 0)
                    events = float(row.get("events", 0) or 0)
                    std_error = float(row.get("event_rate_std_error", np.nan))
                    if n < settings["min_bin_n"]:
                        flags.append("low_bin_n")
                    if events < settings["min_bin_events"]:
                        flags.append("low_events")
                    if np.isfinite(std_error) and std_error > settings["max_event_rate_std_error"]:
                        flags.append("high_event_rate_uncertainty")
                    if flags:
                        variable_alert_count += len(flags)
                        bin_alerts.append(
                            {
                                "variable": variable,
                                "bin_label": row.get("bin_label"),
                                "n": row.get("n"),
                                "events": row.get("events"),
                                "event_rate": row.get("event_rate"),
                                "event_rate_std_error": row.get("event_rate_std_error"),
                                "alert_flags": flags,
                            }
                        )
                variable_status.append(
                    {
                        "variable": variable,
                        "status": "warning" if variable_alert_count else "ok",
                        "alert_count": variable_alert_count,
                        "n_bins": int(len(group)),
                    }
                )

        min_n_bins_metadata = getattr(self, "min_n_bins_metadata_", None)
        min_n_bins_warning_count = 0
        if min_n_bins_metadata and not min_n_bins_metadata.get("min_n_bins_reached", True):
            min_n_bins_warning_count = 1

        sampling_metadata = getattr(self, "sampling_metadata_", None)
        backend_metadata = getattr(self, "backend_metadata_", None)
        fit_rows = (
            self._metadata_int(sampling_metadata, "n_rows_fit")
            or self._metadata_int(backend_metadata, "n_rows_fit")
            or self._profile_n_rows(profile)
        )
        source_rows = (
            self._metadata_int(sampling_metadata, "n_rows_source")
            or self._metadata_int(backend_metadata, "n_rows_source")
            or self._profile_n_rows(source_profile)
            or None
        )
        sample_size_issue = bool(fit_rows and fit_rows < settings["min_fit_rows"])
        sample_comparison = None
        sample_alerts = []
        fit_alerts = []
        missing_sampling_diagnostics = self._build_missing_sampling_diagnostics(
            fit_rows=fit_rows,
            source_rows=source_rows,
        )
        self.missing_sampling_diagnostics_ = missing_sampling_diagnostics or None
        missing_sampling_summary = self._missing_sampling_summary(missing_sampling_diagnostics)
        missing_sampling_alerts = [
            {
                "variable": row["variable"],
                "status": row["status"],
                "alert_flags": row["alert_flags"],
                "message": "Source Spark missing behavior differs from the sampled fit.",
            }
            for row in missing_sampling_diagnostics
            if row.get("status") != "ok"
        ]
        if source_profile_status == "skipped_profile_too_large":
            fit_alerts.append(
                {
                    "status": "warning",
                    "alert_flags": ["profile_too_large"],
                    "message": "Spark source profile aggregation exceeded the configured row guard.",
                }
            )
        if source_profile is not None and not source_profile.empty:
            comparison = self._compare_profiles(
                profile,
                source_profile,
                left_name="fit",
                right_name="source",
            )
            if not comparison.empty:
                event_rate_alerts = self._event_rate_profile_alerts(
                    source_profile,
                    profile,
                    application_name="source",
                    reference_name="fit",
                )
                sample_alerts = [alert for alert in event_rate_alerts if alert["status"] != "ok"]
                comparison_records = self._profile_comparison_records(
                    comparison,
                    left_name="fit",
                    right_name="source",
                )
                bins_missing_in_sample = [
                    {"variable": record["variable"], "bin_label": record["bin_label"]}
                    for record in comparison_records
                    if not record["present_in_fit"] and record["present_in_source"]
                ]
                bins_missing_in_source = [
                    {"variable": record["variable"], "bin_label": record["bin_label"]}
                    for record in comparison_records
                    if record["present_in_fit"] and not record["present_in_source"]
                ]
                max_share_abs_diff = (
                    float(comparison["share_abs_diff"].max())
                    if comparison["share_abs_diff"].notna().any()
                    else None
                )
                if max_share_abs_diff is not None and max_share_abs_diff >= settings["max_sample_share_abs_diff"]:
                    fit_alerts.append(
                        {
                            "status": "warning",
                            "alert_flags": ["sample_share_shift"],
                            "message": (
                                "At least one sampled fit bin has a large share difference versus "
                                "the Spark source profile."
                            ),
                            "max_share_abs_diff": max_share_abs_diff,
                        }
                    )
                sample_comparison = {
                    "status": (
                        "critical"
                        if any(alert["status"] == "critical" for alert in sample_alerts)
                        else (
                            "warning"
                            if sample_alerts
                            or missing_sampling_alerts
                            or bins_missing_in_sample
                            or bins_missing_in_source
                            or any("sample_share_shift" in alert.get("alert_flags", []) for alert in fit_alerts)
                            else "ok"
                        )
                    ),
                    "max_event_rate_abs_diff": (
                        float(comparison["event_rate_abs_diff"].max())
                        if comparison["event_rate_abs_diff"].notna().any()
                        else None
                    ),
                    "max_share_abs_diff": max_share_abs_diff,
                    "max_missing_share_abs_diff": missing_sampling_summary["max_missing_share_abs_diff"],
                    "bins_missing_in_sample": bins_missing_in_sample,
                    "bins_missing_in_source": bins_missing_in_source,
                    "bin_diagnostics": comparison_records,
                    "missing_sampling_summary": missing_sampling_summary,
                    "alerts": sample_alerts,
                }
                sample_size_issue = sample_size_issue or bool(sample_alerts)

        for alert in sample_alerts:
            normalized_flags = list(alert.get("alert_flags", []))
            if alert.get("status") in {"warning", "critical"} and "sample_event_rate_shift" not in normalized_flags:
                normalized_flags.append("sample_event_rate_shift")
            fit_alerts.append({**alert, "alert_flags": normalized_flags})
        fit_alerts.extend(missing_sampling_alerts)
        warning_count = (
            len(bin_alerts)
            + min_n_bins_warning_count
            + len(sample_alerts)
            + len(missing_sampling_alerts)
            + len(fit_alerts)
            + int(sample_size_issue)
        )
        status = (
            "critical"
            if any(alert.get("status") == "critical" for alert in fit_alerts)
            else ("warning" if warning_count else "ok")
        )
        sampling_payload = sampling_metadata if isinstance(sampling_metadata, dict) else {}
        backend_payload = backend_metadata if isinstance(backend_metadata, dict) else {}
        merge_map = getattr(self, "missing_merge_map_", {}) or {}
        return {
            "validation_type": "fit",
            "status": status,
            "backend": backend_payload.get("input_backend", getattr(self, "input_backend_", None)),
            "fit_mode": backend_payload.get("fit_mode", sampling_payload.get("fit_mode")),
            "sampling_applied": sampling_payload.get("sampling_applied"),
            "sample_size_requested": sampling_payload.get("sample_size_requested"),
            "sample_fraction_effective": sampling_payload.get("sample_fraction_effective"),
            "missing_policy": self.missing_policy,
            "settings": settings,
            "summary": {
                "variables_fitted": int(len(variable_status)),
                "n_rows_fit": int(fit_rows),
                "n_rows_source": int(source_rows) if source_rows is not None else None,
                "n_variables": self._profile_variable_count(profile),
                "n_fit_profile_rows": int(len(profile)) if profile is not None else 0,
                "n_source_profile_rows": int(len(source_profile)) if source_profile is not None else 0,
                "variables_with_min_n_bins_warning": min_n_bins_warning_count,
                "bins_with_low_n": int(
                    sum("low_bin_n" in alert["alert_flags"] for alert in bin_alerts)
                ),
                "bins_with_low_events": int(
                    sum("low_events" in alert["alert_flags"] for alert in bin_alerts)
                ),
                "bins_with_high_uncertainty": int(
                    sum("high_event_rate_uncertainty" in alert["alert_flags"] for alert in bin_alerts)
                ),
                "possible_sample_size_issue": sample_size_issue,
                "source_profile_status": source_profile_status,
                "sample_representativeness_status": (
                    sample_comparison.get("status") if sample_comparison else None
                ),
                "missing_sampling_status": missing_sampling_summary["status"],
                "merge_decision_count": int(len(merge_map)),
                **missing_summary,
            },
            "variable_status": variable_status,
            "bin_alerts": bin_alerts,
            "alerts": fit_alerts,
            "min_n_bins_metadata": min_n_bins_metadata,
            "sample_representativeness": sample_comparison,
            "missing_sampling_diagnostics": missing_sampling_diagnostics,
            "merge_decision_summary": {
                "merge_decision_learned_on_sample": bool(merge_map),
                "merge_decision_count": int(len(merge_map)),
                "merge_decision_variables": sorted(str(variable) for variable in merge_map),
                "fit_mode": sampling_payload.get("fit_mode") or backend_payload.get("fit_mode"),
            },
        }

    # ------------------------------------------------------------------
    def _refresh_reference_profile(self) -> None:
        source_profile = getattr(self, "source_profile_", None)
        fit_profile = getattr(self, "fit_profile_", None)
        if source_profile is not None and not source_profile.empty:
            self.reference_profile_ = source_profile.copy()
            self.reference_profile_source_ = "source_profile"
        elif fit_profile is not None and not fit_profile.empty:
            self.reference_profile_ = fit_profile.copy()
            self.reference_profile_source_ = "fit_profile"
        else:
            self.reference_profile_ = None
            self.reference_profile_source_ = "missing"

    # ------------------------------------------------------------------
    def _build_transform_validation_report(
        self,
        *,
        application_profile: pd.DataFrame | None,
        target_available: bool,
        backend: str,
        n_application_rows: int | None = None,
    ) -> dict[str, Any]:
        settings = self._default_validation_settings()
        self.validation_settings_ = settings
        reference_profile = getattr(self, "reference_profile_", None)
        if not target_available:
            return {
                "validation_type": "transform",
                "status": "skipped",
                "backend": backend,
                "missing_policy": self.missing_policy,
                "settings": settings,
                "reason": "target_not_available",
                "reference_profile_source": getattr(self, "reference_profile_source_", "missing"),
                "summary": {
                    "target_available": False,
                    "n_application_rows": n_application_rows,
                    "n_application_profile_rows": 0,
                    "n_alerts": 0,
                },
            }
        if reference_profile is None or reference_profile.empty:
            return {
                "validation_type": "transform",
                "status": "warning",
                "backend": backend,
                "missing_policy": self.missing_policy,
                "settings": settings,
                "reason": "reference_profile_missing",
                "reference_profile_source": getattr(self, "reference_profile_source_", "missing"),
                "summary": {
                    "target_available": True,
                    "n_application_rows": n_application_rows,
                    "n_application_profile_rows": (
                        int(len(application_profile)) if application_profile is not None else 0
                    ),
                    "n_alerts": 1,
                },
            }

        comparison = self._compare_profiles(
            application_profile,
            reference_profile,
            left_name="application",
            right_name="reference",
        )
        event_rate_alerts = self._event_rate_profile_alerts(
            application_profile,
            reference_profile,
            application_name="application",
            reference_name="reference",
        )
        comparison_records = self._profile_comparison_records(
            comparison,
            left_name="application",
            right_name="reference",
        )
        bins_missing_in_application = [
            {"variable": record["variable"], "bin_label": record["bin_label"]}
            for record in comparison_records
            if not record["present_in_application"] and record["present_in_reference"]
        ]
        bins_missing_in_reference = [
            {"variable": record["variable"], "bin_label": record["bin_label"]}
            for record in comparison_records
            if record["present_in_application"] and not record["present_in_reference"]
        ]
        alerts = [alert for alert in event_rate_alerts if alert["status"] != "ok"]
        max_share_abs_diff = (
            float(comparison["share_abs_diff"].max())
            if not comparison.empty and comparison["share_abs_diff"].notna().any()
            else None
        )
        if max_share_abs_diff is not None and max_share_abs_diff >= settings["max_sample_share_abs_diff"]:
            alerts.append(
                {
                    "status": "warning",
                    "alert_flags": ["application_share_shift"],
                    "max_share_abs_diff": max_share_abs_diff,
                    "message": "Application bin share differs materially from the reference profile.",
                }
            )
        if bins_missing_in_application:
            alerts.append(
                {
                    "status": "warning",
                    "alert_flags": ["reference_bins_missing_in_application"],
                    "bins": bins_missing_in_application,
                    "message": "Reference bins are absent from the application profile.",
                }
            )
        if bins_missing_in_reference:
            alerts.append(
                {
                    "status": "warning",
                    "alert_flags": ["application_bins_missing_in_reference"],
                    "bins": bins_missing_in_reference,
                    "message": "Application bins are absent from the reference profile.",
                }
            )
        status = (
            "critical"
            if any(alert["status"] == "critical" for alert in alerts)
            else ("warning" if alerts else "ok")
        )
        resolved_application_rows = (
            int(n_application_rows)
            if n_application_rows is not None
            else self._profile_n_rows(application_profile)
        )
        application_missing_summary = self._missing_summary_from_profile(application_profile)

        return {
            "validation_type": "transform",
            "status": status,
            "backend": backend,
            "missing_policy": self.missing_policy,
            "settings": settings,
            "reference_profile_source": getattr(self, "reference_profile_source_", "missing"),
            "summary": {
                "target_available": True,
                "n_application_rows": resolved_application_rows,
                "n_variables": self._profile_variable_count(application_profile),
                "n_application_profile_rows": int(len(application_profile)) if application_profile is not None else 0,
                "n_alerts": len(alerts),
                "max_event_rate_abs_diff": (
                    float(comparison["event_rate_abs_diff"].max())
                    if not comparison.empty and comparison["event_rate_abs_diff"].notna().any()
                    else None
                ),
                "max_share_abs_diff": (
                    max_share_abs_diff
                ),
                **application_missing_summary,
            },
            "event_rate_status": event_rate_alerts,
            "profile_comparison": comparison_records,
            "bins_missing_in_application": bins_missing_in_application,
            "bins_missing_in_reference": bins_missing_in_reference,
            "alerts": alerts,
        }

    # ------------------------------------------------------------------
    def _validate_transform_pandas(
        self,
        transformed: pd.DataFrame,
        original: pd.DataFrame | pd.Series,
        *,
        backend: str,
    ) -> None:
        target_name = getattr(self, "target_name_", None)
        target = None
        if isinstance(original, pd.DataFrame) and target_name in original.columns:
            target = original[target_name]

        if target is None:
            self.application_profile_ = None
            self.transform_validation_report_ = self._build_transform_validation_report(
                application_profile=None,
                target_available=False,
                backend=backend,
            )
        else:
            n_application_rows = len(original) if isinstance(original, pd.DataFrame) else len(transformed)
            self.application_profile_ = self._build_profile_from_transformed(transformed, target)
            self.transform_validation_report_ = self._build_transform_validation_report(
                application_profile=self.application_profile_,
                target_available=True,
                backend=backend,
                n_application_rows=n_application_rows,
            )
        self.validation_report_ = self.transform_validation_report_

    # ------------------------------------------------------------------
    def _validate_transform_pyspark(self, transformed, original) -> None:
        target_name = getattr(self, "target_name_", None)
        if target_name not in list(original.columns):
            self.application_profile_ = None
            self.transform_validation_report_ = self._build_transform_validation_report(
                application_profile=None,
                target_available=False,
                backend="pyspark",
            )
            self.validation_report_ = self.transform_validation_report_
            return

        feature_columns = list(transformed.columns)
        n_application_rows = int(original.count())
        self.application_profile_ = self._build_bin_profile_pyspark(
            original,
            target_name=target_name,
            feature_columns=feature_columns,
            n_rows=n_application_rows,
        )
        self.transform_validation_report_ = self._build_transform_validation_report(
            application_profile=self.application_profile_,
            target_available=True,
            backend="pyspark",
            n_application_rows=n_application_rows,
        )
        self.validation_report_ = self.transform_validation_report_

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
        self.data_schema_ = self.describe_schema()
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
                stacklevel=2,
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
        validate: bool = False,
    ):
        """Fit binning rules on one or more columns."""
        time_col = time_col or self.time_col
        backend = detect_dataframe_backend(X, argument_name="X")
        if backend == "pyspark":
            return self._fit_pyspark(
                X,
                y,
                target=target,
                column=column,
                columns=columns,
                feature=feature,
                features=features,
                time_col=time_col,
                copy=copy,
                validate=validate,
            )

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
        self.fit_validation_report_ = None
        self.transform_validation_report_ = None
        self.validation_report_ = None
        self.application_profile_ = None
        self.source_profile_ = None
        self.source_missing_counts_ = None
        self.missing_sampling_diagnostics_ = None
        self.missing_profile_ = pd.DataFrame()
        self.missing_decision_log_ = pd.DataFrame()
        self.missing_merge_candidates_ = pd.DataFrame()
        self.missing_merge_map_ = {}
        self._missing_merge_metrics_ = {}
        self.missing_transform_fallback_log_ = pd.DataFrame()
        self.missing_policy_ = self.missing_policy
        self.effective_missing_policy_ = self.missing_policy
        self.missing_merge_criterion_ = self.missing_merge_criterion
        self.missing_merge_fallback_ = self.missing_merge_fallback
        self.validation_settings_ = None
        self.sampling_metadata_ = self._pandas_fit_sampling_metadata(len(X))
        self.input_backend_ = "pandas"
        self.fit_backend_ = "pandas_core"
        self.backend_metadata_ = {
            "input_backend": "pandas",
            "fit_backend": "pandas_core",
            "fit_mode": "pandas_core",
            "n_rows_source": int(len(X)),
            "n_rows_fit": int(len(X)),
        }
        X_features = X.drop(columns=[time_col], errors="ignore") if time_col else X.copy()
        self._check_missing_policy_pandas(X_features, selected_features, context="fit")

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
                missing_policy=self.missing_policy,
                missing_merge_criterion=self.missing_merge_criterion,
                missing_merge_fallback=self.missing_merge_fallback,
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
            self._refresh_min_n_bins_metadata()
            self._finalize_fit_missing_audit(X_features, y, backend="pandas")
            self._refresh_reference_profile()
            if validate:
                self.fit_validation_report_ = self._build_fit_validation_report()
                self.validation_report_ = self.fit_validation_report_
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

            summary = self._refine_bins_for_policy(
                strat.bin_summary_,
                min_er_delta=self.min_event_rate_diff,
                trend=self.monotonic,
                time_col=time_col,
                check_stability=self.check_stability,
            )
            summary = self._filter_fitted_summary(summary)
            summary = self._prepare_binning_summary(summary)

            self._per_feature_binners[col] = strat
            summaries.append(summary)

        for col in cat_cols:
            from .strategies.categorical import CategoricalBinning

            strat = CategoricalBinning(
                max_bins=self.max_bins,
                separate_missing=self._uses_explicit_missing_bin(),
            )
            strat.fit(X_features[[col]], y)

            summary = self._refine_bins_for_policy(
                strat.bin_summary_,
                min_er_delta=self.min_event_rate_diff,
                trend=None,
                time_col=None,
                check_stability=False,
            )
            summary = self._filter_fitted_summary(summary)
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
        self._refresh_min_n_bins_metadata()
        self._finalize_fit_missing_audit(X_features, y, backend="pandas")
        self._refresh_reference_profile()
        if validate:
            self.fit_validation_report_ = self._build_fit_validation_report()
            self.validation_report_ = self.fit_validation_report_
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
        validate: bool = False,
    ):
        """Apply fitted bins to new data."""
        original_input = X
        backend = detect_dataframe_backend(X, argument_name="X")
        if backend == "pyspark":
            return self._transform_pyspark(
                X,
                column=column,
                columns=columns,
                feature=feature,
                features=features,
                return_woe=return_woe,
                return_type=return_type,
                validate=validate,
            )

        X, selected_columns, input_kind = self._normalize_transform_input(
            X,
            column=column,
            columns=columns,
            feature=feature,
            features=features,
            copy=copy,
        )
        X = self._coerce_force_numeric_columns(X, columns=selected_columns)
        self._check_missing_policy_pandas(X, selected_columns, context="transform")

        core_return_woe = return_woe and self.missing_policy != _MERGE_MISSING_POLICY
        transformed_df = self._transform_pandas_core(
            X,
            selected_columns,
            return_woe=core_return_woe,
        )
        transformed_df = self._route_missing_merge_pandas(transformed_df, X, selected_columns)
        if return_woe and self.missing_policy == _MERGE_MISSING_POLICY:
            transformed_df = self._map_missing_merge_labels_to_woe(transformed_df, selected_columns)
        if validate:
            self._validate_transform_pandas(transformed_df, original_input, backend="pandas")
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
    def export_bundle(self, path: str, *, include_audit_report: bool = True) -> None:
        """Export a complete audit bundle with JSON and tabular artifacts."""
        from .reporting import export_binner_bundle

        self._ensure_fitted()
        export_binner_bundle(self, path, include_audit_report=include_audit_report)

    # ------------------------------------------------------------------
    def export_audit_report(
        self,
        path: str,
        *,
        title: str | None = None,
        dataset_name: str | None = None,
    ) -> None:
        """Export a standalone narrative audit report as self-contained HTML."""
        from .audit_report import export_audit_report_html

        self._ensure_fitted()
        export_audit_report_html(self, path, title=title, dataset_name=dataset_name)

    # ------------------------------------------------------------------
    def save_report(self, path: str) -> None:
        from .reporting import save_binner_report

        save_binner_report(self, path)
