"""Internal dataframe backend detection helpers."""

from __future__ import annotations

from importlib.util import find_spec
from typing import Literal

import pandas as pd

DataFrameBackend = Literal["pandas", "pyspark"]


def _pyspark_dataframe_class():
    if find_spec("pyspark") is None:
        return None
    try:
        from pyspark.sql import DataFrame as SparkDataFrame
    except Exception:  # pragma: no cover - optional dependency import guard
        return None
    return SparkDataFrame


def detect_dataframe_backend(obj: object, *, argument_name: str = "X") -> DataFrameBackend:
    """Return the supported dataframe backend for an input object."""
    if isinstance(obj, (pd.DataFrame, pd.Series)):
        return "pandas"

    spark_dataframe = _pyspark_dataframe_class()
    if spark_dataframe is not None and isinstance(obj, spark_dataframe):
        return "pyspark"

    type_name = f"{type(obj).__module__}.{type(obj).__qualname__}"
    raise TypeError(
        f"`{argument_name}` must be a pandas DataFrame/Series or a PySpark DataFrame; "
        f"got {type_name}."
    )
