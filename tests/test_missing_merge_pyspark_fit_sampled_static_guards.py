import inspect

import pytest

from riskbands.binning_engine import Binner


def test_sampled_fit_to_pandas_is_limited_to_sample_or_empty_sample_fallback():
    source = inspect.getsource(Binner._fit_pyspark)

    assert "sampled_spark.toPandas()" in source
    assert "selected_spark.limit(1).toPandas()" in source
    assert "X.toPandas(" not in source
    assert "selected_spark.toPandas(" not in source


def test_sampled_fit_does_not_use_spark_native_missing_merge_or_udf():
    fit_source = inspect.getsource(Binner._fit_pyspark)
    transform_sources = "\n".join(
        inspect.getsource(getattr(Binner, method_name))
        for method_name in (
            "_transform_pyspark",
            "_spark_transform_expression",
            "_numeric_supervised_spark_expression",
            "_numeric_unsupervised_spark_expression",
            "_categorical_spark_expression",
        )
    )

    assert "self.fit(" in fit_source
    assert "sample_pdf" in fit_source
    assert "groupBy(" not in fit_source
    for token in ("udf(", "pandas_udf", "UserDefinedFunction"):
        assert token not in fit_source
        assert token not in transform_sources


@pytest.mark.parametrize(
    "method_name,allowed_token",
    [
        ("_pyspark_missing_counts", ".collect("),
        ("_collect_pyspark_profile_aggregate", ".toPandas("),
    ],
)
def test_collect_and_to_pandas_are_confined_to_named_aggregate_or_sampling_helpers(
    method_name,
    allowed_token,
):
    source = inspect.getsource(getattr(Binner, method_name))

    assert allowed_token in source
    assert ".toPandas(" not in inspect.getsource(Binner._pyspark_missing_counts)
    assert ".collect(" not in inspect.getsource(Binner._collect_pyspark_profile_aggregate)
