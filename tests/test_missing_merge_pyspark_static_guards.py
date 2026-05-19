import inspect

import pytest

from riskbands.binning_engine import Binner

DIRECT_SPARK_TRANSFORM_METHODS = [
    "_check_missing_policy_pyspark",
    "_transform_pyspark",
    "_spark_transform_expression",
    "_numeric_supervised_spark_expression",
    "_numeric_unsupervised_spark_expression",
    "_categorical_spark_expression",
]

FORBIDDEN_DIRECT_TOKENS = [
    ".toPandas(",
    ".collect(",
    "udf(",
    "pandas_udf",
    "UserDefinedFunction",
]


@pytest.mark.parametrize("method_name", DIRECT_SPARK_TRANSFORM_METHODS)
def test_spark_missing_merge_direct_transform_path_has_no_udf_or_full_collect(method_name):
    source = inspect.getsource(getattr(Binner, method_name))

    for token in FORBIDDEN_DIRECT_TOKENS:
        assert token not in source


def test_spark_collect_exceptions_are_limited_to_named_aggregate_helpers():
    allowed_collect_helpers = {
        "_pyspark_missing_counts": ".collect(",
        "_collect_pyspark_profile_aggregate": ".toPandas(",
    }

    for method_name, expected_token in allowed_collect_helpers.items():
        source = inspect.getsource(getattr(Binner, method_name))
        assert expected_token in source

    assert ".toPandas(" not in inspect.getsource(Binner._pyspark_missing_counts)
    assert ".collect(" not in inspect.getsource(Binner._collect_pyspark_profile_aggregate)
