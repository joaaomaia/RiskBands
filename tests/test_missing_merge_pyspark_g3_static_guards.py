import inspect

from riskbands.binning_engine import Binner


def test_source_profile_uses_guarded_aggregate_collection_only():
    source = inspect.getsource(Binner._build_bin_profile_pyspark)

    assert ".groupBy(" in source
    assert "_collect_pyspark_profile_aggregate(" in source
    assert ".toPandas(" not in source
    assert ".collect(" not in source


def test_profile_aggregate_helper_checks_row_guard_before_to_pandas():
    source = inspect.getsource(Binner._collect_pyspark_profile_aggregate)

    assert "limit(remaining_rows + 1).count()" in source
    assert "profile_sdf.toPandas()" in source
    assert source.index("limit(remaining_rows + 1).count()") < source.index("profile_sdf.toPandas()")
    assert ".collect(" not in source


def test_spark_fit_to_pandas_is_confined_to_sampled_fit_boundary():
    source = inspect.getsource(Binner._fit_pyspark)

    assert "sampled_spark.toPandas()" in source
    assert "selected_spark.limit(1).toPandas()" in source
    assert "X.toPandas(" not in source
    assert "selected_spark.toPandas(" not in source
    assert ".collect(" not in source


def test_transform_validation_path_has_no_full_collect_or_udf():
    methods = [
        "_validate_transform_pyspark",
        "_build_transform_validation_report",
        "_transform_pyspark",
        "_spark_transform_expression",
        "_numeric_supervised_spark_expression",
        "_numeric_unsupervised_spark_expression",
        "_categorical_spark_expression",
    ]

    for method_name in methods:
        source = inspect.getsource(getattr(Binner, method_name))
        assert ".toPandas(" not in source
        assert ".collect(" not in source
        assert "udf(" not in source
        assert "pandas_udf" not in source
        assert "UserDefinedFunction" not in source


def test_collect_and_to_pandas_remain_limited_to_named_helpers_or_sampling():
    allowed_to_pandas = {
        "_fit_pyspark",
        "_collect_pyspark_profile_aggregate",
    }
    allowed_collect = {
        "_pyspark_missing_counts",
    }
    violations = []
    for method_name, method in inspect.getmembers(Binner, predicate=inspect.isfunction):
        source = inspect.getsource(method)
        if ".toPandas(" in source and method_name not in allowed_to_pandas:
            violations.append((method_name, ".toPandas("))
        if ".collect(" in source and method_name not in allowed_collect:
            violations.append((method_name, ".collect("))

    assert violations == []
