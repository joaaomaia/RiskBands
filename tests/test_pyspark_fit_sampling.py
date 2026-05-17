import math

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal

from riskbands import RiskBands
from riskbands.utils import dataframe_backend


class FakeSparkDataFrame:
    def __init__(self, pdf: pd.DataFrame, ops: dict | None = None):
        self._pdf = pdf.copy()
        self.ops = ops if ops is not None else {
            "selects": [],
            "samples": [],
            "limits": [],
            "to_pandas_columns": [],
        }

    @property
    def columns(self):
        return list(self._pdf.columns)

    def count(self):
        return len(self._pdf)

    def select(self, *columns):
        selected = list(columns)
        self.ops["selects"].append(selected)
        return FakeSparkDataFrame(self._pdf.loc[:, selected], self.ops)

    def sample(self, *, withReplacement=False, fraction=None, seed=None):
        self.ops["samples"].append(
            {
                "withReplacement": withReplacement,
                "fraction": fraction,
                "seed": seed,
            }
        )
        n = min(len(self._pdf), math.ceil(len(self._pdf) * float(fraction)))
        sampled = self._pdf.sample(n=n, random_state=seed) if n else self._pdf.head(0)
        return FakeSparkDataFrame(sampled, self.ops)

    def limit(self, n):
        self.ops["limits"].append(n)
        return FakeSparkDataFrame(self._pdf.head(n), self.ops)

    def toPandas(self):
        self.ops["to_pandas_columns"].append(list(self._pdf.columns))
        return self._pdf.copy()


def make_frame(n=180, seed=71):
    rng = np.random.default_rng(seed)
    score = rng.normal(size=n)
    target = (score + rng.normal(scale=0.35, size=n) > 0).astype(int)
    return pd.DataFrame(
        {
            "score": score,
            "noise": rng.normal(size=n),
            "month": rng.choice([202401, 202402, 202403], size=n),
            "target": target,
        }
    )


def patch_fake_pyspark(monkeypatch):
    monkeypatch.setattr(dataframe_backend, "_pyspark_dataframe_class", lambda: FakeSparkDataFrame)


def test_fit_accepts_pyspark_dataframe_via_sampled_pandas_core(monkeypatch):
    patch_fake_pyspark(monkeypatch)
    spark_df = FakeSparkDataFrame(make_frame())
    binner = RiskBands(strategy="supervised", max_bins=3, min_event_rate_diff=0.0, sample_size=40)

    binner.fit(spark_df, target="target", column="score")

    assert binner.input_backend_ == "pyspark"
    assert binner.fit_backend_ == "pandas_core"
    assert binner.backend_metadata_["fit_mode"] == "sampled_to_pandas"
    assert not binner.binning_table().empty
    assert spark_df.ops["selects"] == [["score", "target"]]
    assert spark_df.ops["to_pandas_columns"] == [["score", "target"]]


def test_pyspark_absolute_sample_size_limits_collected_rows(monkeypatch):
    patch_fake_pyspark(monkeypatch)
    spark_df = FakeSparkDataFrame(make_frame(n=160))
    binner = RiskBands(strategy="supervised", max_bins=3, min_event_rate_diff=0.0, sample_size=30)

    binner.fit(spark_df, target="target", column="score")

    assert binner.sampling_metadata_["sample_size_type"] == "absolute"
    assert binner.sampling_metadata_["n_rows_source"] == 160
    assert binner.sampling_metadata_["n_rows_fit"] <= 30
    assert spark_df.ops["limits"] == [30]


def test_pyspark_fractional_sample_size_uses_fraction(monkeypatch):
    patch_fake_pyspark(monkeypatch)
    spark_df = FakeSparkDataFrame(make_frame(n=160))
    binner = RiskBands(strategy="supervised", max_bins=3, min_event_rate_diff=0.0, sample_size=0.25)

    binner.fit(spark_df, target="target", column="score")

    assert binner.sampling_metadata_["sample_size_type"] == "fraction"
    assert binner.sampling_metadata_["sample_fraction_effective"] == 0.25
    assert binner.sampling_metadata_["n_rows_source"] == 160
    assert binner.sampling_metadata_["n_rows_fit"] == 40
    assert spark_df.ops["samples"][0]["fraction"] == 0.25


def test_pyspark_fit_collects_only_needed_feature_target_and_time_columns(monkeypatch):
    patch_fake_pyspark(monkeypatch)
    spark_df = FakeSparkDataFrame(make_frame(n=120))
    binner = RiskBands(strategy="supervised", max_bins=3, min_event_rate_diff=0.0, sample_size=50)

    binner.fit(spark_df, target="target", column="score", time_col="month")

    assert spark_df.ops["selects"] == [["score", "month", "target"]]
    assert binner.backend_metadata_["collected_columns"] == ["score", "month", "target"]
    assert binner.backend_metadata_["source_columns"] == ["score", "noise", "month", "target"]


def test_pandas_fit_is_not_sampled_by_sample_size():
    df = make_frame()
    small_sample_setting = RiskBands(strategy="supervised", max_bins=3, min_event_rate_diff=0.0, sample_size=10)
    large_sample_setting = RiskBands(strategy="supervised", max_bins=3, min_event_rate_diff=0.0, sample_size=10_000)

    small_sample_setting.fit(df, y="target", column="score")
    large_sample_setting.fit(df, y="target", column="score")

    assert small_sample_setting.backend_metadata_["fit_mode"] == "pandas_core"
    assert small_sample_setting.backend_metadata_["n_rows_fit"] == len(df)
    assert small_sample_setting.sampling_metadata_["sampling_applied"] is False
    assert small_sample_setting.sampling_metadata_["sampling_strategy"] == "none"
    assert small_sample_setting.sampling_metadata_["n_rows_fit"] == len(df)
    assert_frame_equal(small_sample_setting.binning_table(), large_sample_setting.binning_table())
