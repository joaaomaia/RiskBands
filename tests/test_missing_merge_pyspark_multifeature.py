from collections import Counter

import numpy as np
import pandas as pd
import pytest

from riskbands import RiskBands

pytestmark = pytest.mark.spark
pytest_plugins = ["tests.test_missing_values_pyspark_current_behavior"]


def _make_mixed_fit_frame():
    rows = []
    specs = [
        (-5.0, -50.0, "A", 4, 40),
        (-3.0, -30.0, "A", 8, 40),
        (0.0, 0.0, "B", 20, 40),
        (3.0, 30.0, "C", 32, 40),
        (5.0, 50.0, "C", 36, 40),
    ]
    for score_a, score_b, rating, events, n_rows in specs:
        targets = [1] * events + [0] * (n_rows - events)
        for idx, target in enumerate(targets):
            rows.append(
                {
                    "score_a": score_a,
                    "score_b": score_b + (idx % 3) * 0.01,
                    "rating": rating,
                    "target": target,
                }
            )
    for idx, target in enumerate([1] * 20 + [0] * 20):
        rows.append(
            {
                "score_a": np.nan,
                "score_b": 10.0 + (idx % 3) * 0.01,
                "rating": None,
                "target": target,
            }
        )
    return pd.DataFrame(rows)


def _fit_mixed_binner(criterion):
    return RiskBands(
        max_bins=5,
        min_event_rate_diff=0.0,
        force_categorical=["rating"],
        missing_policy="merge",
        missing_merge_criterion=criterion,
        missing_merge_fallback="separate_bin",
    ).fit(
        _make_mixed_fit_frame(),
        y="target",
        columns=["score_a", "score_b", "rating"],
    )


def _mixed_spark_frame(spark_session):
    from pyspark.sql import types as T

    schema = T.StructType(
        [
            T.StructField("score_a", T.DoubleType(), True),
            T.StructField("score_b", T.DoubleType(), True),
            T.StructField("rating", T.StringType(), True),
            T.StructField("segment", T.StringType(), True),
        ]
    )
    rows = [
        (None, None, None, "extra-a"),
        (float("nan"), float("nan"), "A", "extra-b"),
        (-5.0, -50.0, "Z", "extra-c"),
        (0.0, 0.0, "B", "extra-d"),
        (5.0, 50.0, "C", "extra-e"),
    ]
    return spark_session.createDataFrame(rows, schema=schema)


def _column_values(spark_df, column):
    return [row[column] for row in spark_df.select(column).collect()]


def _string_counts(values):
    return Counter(str(value) for value in values)


@pytest.mark.parametrize("criterion", ["nearest_event_rate", "nearest_woe"])
def test_multifeature_subset_transform_uses_column_merge_maps_and_drops_extras(
    spark_session,
    criterion,
):
    binner = _fit_mixed_binner(criterion)
    spark_df = _mixed_spark_frame(spark_session)

    transformed = binner.transform(spark_df, columns=["score_a", "rating"])

    assert transformed.columns == ["score_a", "rating"]
    assert "segment" not in transformed.columns
    assert "score_b" not in transformed.columns
    assert _string_counts(_column_values(transformed, "score_a"))[
        str(binner.missing_merge_map_["score_a"])
    ] >= 2
    assert _string_counts(_column_values(transformed, "rating"))[
        str(binner.missing_merge_map_["rating"])
    ] >= 1
    assert "Missing" not in _string_counts(_column_values(transformed, "score_a"))
    assert "Missing" not in _string_counts(_column_values(transformed, "rating"))


@pytest.mark.parametrize("criterion", ["nearest_event_rate", "nearest_woe"])
def test_multifeature_all_columns_uses_separate_fallback_only_for_column_without_decision(
    spark_session,
    criterion,
):
    binner = _fit_mixed_binner(criterion)
    assert set(binner.missing_merge_map_) == {"score_a", "rating"}
    spark_df = _mixed_spark_frame(spark_session)

    transformed = binner.transform(spark_df, columns=["score_a", "score_b", "rating"])

    assert transformed.columns == ["score_a", "score_b", "rating"]
    assert _string_counts(_column_values(transformed, "score_a"))[
        str(binner.missing_merge_map_["score_a"])
    ] >= 2
    assert _string_counts(_column_values(transformed, "rating"))[
        str(binner.missing_merge_map_["rating"])
    ] >= 1
    assert _string_counts(_column_values(transformed, "score_b"))["Missing"] == 2
