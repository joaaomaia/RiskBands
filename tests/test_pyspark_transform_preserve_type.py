import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal

from riskbands import RiskBands
from riskbands.utils import dataframe_backend


class Expr:
    def __init__(self, func):
        self._func = func

    def eval(self, pdf):
        value = self._func(pdf)
        if isinstance(value, pd.Series):
            return value
        return pd.Series([value] * len(pdf), index=pdf.index)

    @staticmethod
    def _expr(value):
        return value if isinstance(value, Expr) else Expr(lambda pdf: value)

    def __lt__(self, other):
        other = self._expr(other)
        return Expr(lambda pdf: self.eval(pdf) < other.eval(pdf))

    def __ge__(self, other):
        other = self._expr(other)
        return Expr(lambda pdf: self.eval(pdf) >= other.eval(pdf))

    def __eq__(self, other):
        other = self._expr(other)
        return Expr(lambda pdf: self.eval(pdf) == other.eval(pdf))

    def __and__(self, other):
        other = self._expr(other)
        return Expr(lambda pdf: self.eval(pdf).fillna(False) & other.eval(pdf).fillna(False))

    def __or__(self, other):
        other = self._expr(other)
        return Expr(lambda pdf: self.eval(pdf).fillna(False) | other.eval(pdf).fillna(False))

    def __invert__(self):
        return Expr(lambda pdf: ~self.eval(pdf).fillna(False))

    def isNull(self):
        return Expr(lambda pdf: self.eval(pdf).isna())

    def isNotNull(self):
        return Expr(lambda pdf: self.eval(pdf).notna())

    def cast(self, dtype):
        if dtype == "string":
            return Expr(lambda pdf: self.eval(pdf).astype(str))
        if dtype in {"double", "float"}:
            return Expr(lambda pdf: pd.to_numeric(self.eval(pdf), errors="coerce").astype(float))
        if dtype in {"int", "integer", "long"}:
            return Expr(lambda pdf: pd.to_numeric(self.eval(pdf), errors="coerce"))
        if dtype != "string":
            raise NotImplementedError(dtype)


class Aggregate:
    def __init__(self, op, expr):
        self.op = op
        self.expr = Expr._expr(expr)
        self.name = op

    def alias(self, name):
        self.name = name
        return self


class WhenBuilder:
    def __init__(self, condition, value):
        self.cases = [(condition, Expr._expr(value))]

    def when(self, condition, value):
        self.cases.append((condition, Expr._expr(value)))
        return self

    def otherwise(self, value):
        default = Expr._expr(value)

        def evaluate(pdf):
            result = default.eval(pdf).astype(object)
            matched = pd.Series(False, index=pdf.index)
            for condition, case_value in self.cases:
                mask = condition.eval(pdf).fillna(False) & ~matched
                case_series = case_value.eval(pdf)
                result.loc[mask] = case_series.loc[mask]
                matched |= mask
            return result

        return Expr(evaluate)


class FakeFunctions:
    udf_called = False

    @staticmethod
    def col(name):
        return Expr(lambda pdf: pdf[name])

    @staticmethod
    def lit(value):
        return Expr(lambda pdf: value)

    @staticmethod
    def isnan(expr):
        return Expr(lambda pdf: expr.eval(pdf).map(lambda value: isinstance(value, float) and np.isnan(value)))

    @staticmethod
    def coalesce(*exprs):
        exprs = [Expr._expr(expr) for expr in exprs]

        def evaluate(pdf):
            result = exprs[0].eval(pdf).copy()
            for expr in exprs[1:]:
                result = result.combine_first(expr.eval(pdf))
            return result

        return Expr(evaluate)

    @staticmethod
    def count(expr):
        return Aggregate("count", expr)

    @staticmethod
    def sum(expr):
        return Aggregate("sum", expr)

    @staticmethod
    def when(condition, value):
        return WhenBuilder(condition, value)

    @staticmethod
    def udf(*args, **kwargs):
        FakeFunctions.udf_called = True
        raise AssertionError("Spark transform must not use Python UDFs")


class FakeSparkDataFrame:
    def __init__(self, pdf: pd.DataFrame, ops: dict | None = None):
        self._pdf = pdf.copy()
        self.ops = ops if ops is not None else {"with_columns": [], "selects": []}

    @property
    def columns(self):
        return list(self._pdf.columns)

    def withColumn(self, name, expr):
        self.ops["with_columns"].append(name)
        next_pdf = self._pdf.copy()
        next_pdf[name] = expr.eval(next_pdf)
        return FakeSparkDataFrame(next_pdf, self.ops)

    def select(self, *columns):
        selected = list(columns)
        self.ops["selects"].append(selected)
        return FakeSparkDataFrame(self._pdf.loc[:, selected], self.ops)

    def groupBy(self, *columns):
        return FakeGroupedData(self, columns)

    def limit(self, n):
        return FakeSparkDataFrame(self._pdf.head(n), self.ops)

    def count(self):
        return len(self._pdf)

    def toPandas(self):
        return self._pdf.copy()


class FakeGroupedData:
    def __init__(self, frame, columns):
        self.frame = frame
        self.columns = list(columns)

    def agg(self, *aggregates):
        grouped = self.frame._pdf.groupby(self.columns, sort=False, dropna=False)
        records = []
        for key, group in grouped:
            key_values = key if isinstance(key, tuple) else (key,)
            row = dict(zip(self.columns, key_values, strict=True))
            for aggregate in aggregates:
                values = aggregate.expr.eval(group)
                if aggregate.op == "count":
                    row[aggregate.name] = int(len(group))
                elif aggregate.op == "sum":
                    row[aggregate.name] = float(pd.to_numeric(values, errors="coerce").sum(skipna=True))
                else:
                    raise NotImplementedError(aggregate.op)
            records.append(row)
        return FakeSparkDataFrame(pd.DataFrame(records), self.frame.ops)


def make_frame(n=300, seed=83):
    rng = np.random.default_rng(seed)
    score = np.linspace(-3, 3, n)
    proba = 1 / (1 + np.exp(-2 * score))
    target = (rng.random(n) < proba).astype(int)
    return pd.DataFrame({"score": score, "target": target})


def patch_fake_pyspark(monkeypatch):
    FakeFunctions.udf_called = False
    monkeypatch.setattr(dataframe_backend, "_pyspark_dataframe_class", lambda: FakeSparkDataFrame)
    monkeypatch.setattr(RiskBands, "_spark_functions", staticmethod(lambda: FakeFunctions))


def fit_reference_binner():
    df = make_frame()
    binner = RiskBands(strategy="supervised", max_bins=4, min_event_rate_diff=0.0)
    binner.fit(df, y="target", column="score")
    return binner


def test_transform_pandas_returns_pandas_dataframe():
    binner = fit_reference_binner()
    data = pd.DataFrame({"score": [-10.0, 0.0, 10.0]})

    transformed = binner.transform(data)

    assert isinstance(transformed, pd.DataFrame)
    assert list(transformed.columns) == ["score"]


def test_transform_pyspark_returns_pyspark_dataframe(monkeypatch):
    patch_fake_pyspark(monkeypatch)
    binner = fit_reference_binner()
    spark_df = FakeSparkDataFrame(pd.DataFrame({"score": [-10.0, 0.0, 10.0], "extra": [1, 2, 3]}))

    transformed = binner.transform(spark_df, column="score")

    assert isinstance(transformed, FakeSparkDataFrame)
    assert transformed.columns == ["score"]
    assert spark_df.ops["with_columns"] == ["score"]
    assert spark_df.ops["selects"] == [["score"]]


def test_transform_pyspark_uses_native_expression_path_without_udf(monkeypatch):
    patch_fake_pyspark(monkeypatch)
    binner = fit_reference_binner()
    spark_df = FakeSparkDataFrame(pd.DataFrame({"score": [-10.0, 0.0, 10.0]}))

    binner.transform(spark_df)

    assert FakeFunctions.udf_called is False


def test_transform_pandas_and_pyspark_match_for_nulls_boundaries_and_extremes(monkeypatch):
    patch_fake_pyspark(monkeypatch)
    binner = fit_reference_binner()
    splits = list(binner._per_feature_binners["score"].models_["score"].splits)
    values = [-1e9, splits[0], (splits[0] + splits[1]) / 2, splits[-1], 1e9, np.nan]
    pandas_df = pd.DataFrame({"score": values})
    spark_df = FakeSparkDataFrame(pandas_df)

    pandas_transformed = binner.transform(pandas_df).reset_index(drop=True)
    spark_transformed = binner.transform(spark_df).toPandas().reset_index(drop=True)

    assert_frame_equal(spark_transformed, pandas_transformed, check_dtype=False)
