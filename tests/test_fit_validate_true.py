import json
import math

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal

from riskbands import RiskBands
from riskbands.utils import dataframe_backend
from tests.test_pyspark_transform_preserve_type import FakeFunctions


class ValidatingFakeSparkDataFrame:
    def __init__(self, pdf: pd.DataFrame, ops: dict | None = None, sample_mode: str = "random"):
        self._pdf = pdf.copy()
        self.sample_mode = sample_mode
        self.ops = ops if ops is not None else {
            "selects": [],
            "samples": [],
            "limits": [],
            "with_columns": [],
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
        return ValidatingFakeSparkDataFrame(self._pdf.loc[:, selected], self.ops, self.sample_mode)

    def sample(self, *, withReplacement=False, fraction=None, seed=None):
        self.ops["samples"].append({"fraction": fraction, "seed": seed})
        n = min(len(self._pdf), math.ceil(len(self._pdf) * float(fraction)))
        if self.sample_mode == "head":
            sample = self._pdf.head(n)
        else:
            sample = self._pdf.sample(n=n, random_state=seed)
        return ValidatingFakeSparkDataFrame(sample, self.ops, self.sample_mode)

    def limit(self, n):
        self.ops["limits"].append(n)
        return ValidatingFakeSparkDataFrame(self._pdf.head(n), self.ops, self.sample_mode)

    def withColumn(self, name, expr):
        self.ops["with_columns"].append(name)
        next_pdf = self._pdf.copy()
        next_pdf[name] = expr.eval(next_pdf)
        return ValidatingFakeSparkDataFrame(next_pdf, self.ops, self.sample_mode)

    def groupBy(self, *columns):
        return ValidatingFakeGroupedData(self, columns)

    def toPandas(self):
        self.ops["to_pandas_columns"].append(list(self._pdf.columns))
        return self._pdf.copy()


class ValidatingFakeGroupedData:
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
        return ValidatingFakeSparkDataFrame(pd.DataFrame(records), self.frame.ops, self.frame.sample_mode)


def make_frame(n=220, seed=101):
    rng = np.random.default_rng(seed)
    score = np.linspace(-3, 3, n)
    proba = 1 / (1 + np.exp(-2 * score))
    target = (rng.random(n) < proba).astype(int)
    return pd.DataFrame({"score": score, "target": target})


def patch_fake_pyspark(monkeypatch):
    FakeFunctions.udf_called = False
    monkeypatch.setattr(dataframe_backend, "_pyspark_dataframe_class", lambda: ValidatingFakeSparkDataFrame)
    monkeypatch.setattr(RiskBands, "_spark_functions", staticmethod(lambda: FakeFunctions))


def test_fit_validate_true_creates_validation_report_and_bundle_payload(tmp_path):
    df = make_frame()
    binner = RiskBands(strategy="supervised", max_bins=4, min_event_rate_diff=0.0)

    binner.fit(df, y="target", column="score", validate=True)
    binner.export_bundle(tmp_path / "bundle")
    manifest = json.loads((tmp_path / "bundle" / "metadata.json").read_text(encoding="utf-8"))

    assert binner.validation_report_["validation_type"] == "fit"
    assert binner.fit_validation_report_ is binner.validation_report_
    assert "summary" in binner.validation_report_
    assert "bin_alerts" in binner.validation_report_
    assert "validation_report" in manifest
    assert "fit_validation_report" in manifest


def test_fit_validate_false_does_not_create_detailed_validation_report():
    df = make_frame()
    binner = RiskBands(strategy="supervised", max_bins=4, min_event_rate_diff=0.0)

    binner.fit(df, y="target", column="score", validate=False)

    assert binner.validation_report_ is None
    assert binner.fit_validation_report_ is None
    assert binner.validation_settings_ is None


def test_fit_validate_true_does_not_change_binnings():
    df = make_frame()
    base = RiskBands(strategy="supervised", max_bins=4, min_event_rate_diff=0.0)
    validated = RiskBands(strategy="supervised", max_bins=4, min_event_rate_diff=0.0)

    base.fit(df, y="target", column="score", validate=False)
    validated.fit(df, y="target", column="score", validate=True)

    assert_frame_equal(base.binning_table(), validated.binning_table())


def test_fit_validate_true_flags_low_event_bins():
    df = pd.DataFrame({"score": np.arange(120), "target": np.zeros(120, dtype=int)})
    df.loc[0, "target"] = 1
    binner = RiskBands(strategy="unsupervised", max_bins=4)

    binner.fit(df, y="target", column="score", validate=True)

    assert binner.validation_report_["summary"]["bins_with_low_events"] > 0
    assert any("low_events" in alert["alert_flags"] for alert in binner.validation_report_["bin_alerts"])


def test_fit_spark_validate_true_creates_fit_and_source_profiles(monkeypatch):
    patch_fake_pyspark(monkeypatch)
    spark_df = ValidatingFakeSparkDataFrame(make_frame(n=160))
    binner = RiskBands(strategy="supervised", max_bins=3, min_event_rate_diff=0.0, sample_size=60)

    binner.fit(spark_df, target="target", column="score", validate=True)

    assert not binner.fit_profile_.empty
    assert binner.source_profile_ is not None
    assert not binner.source_profile_.empty
    assert binner.validation_report_["summary"]["source_profile_status"] == "computed"
    assert binner.fit_validation_report_ is binner.validation_report_
    assert spark_df.ops["with_columns"]


def test_fit_spark_validate_false_skips_source_profile_aggregation(monkeypatch):
    patch_fake_pyspark(monkeypatch)
    spark_df = ValidatingFakeSparkDataFrame(make_frame(n=160))
    binner = RiskBands(strategy="supervised", max_bins=3, min_event_rate_diff=0.0, sample_size=60)

    binner.fit(spark_df, target="target", column="score", validate=False)

    assert binner.source_profile_ is None
    assert binner.validation_report_ is None
    assert spark_df.ops["with_columns"] == []


def test_fit_spark_validate_true_flags_sample_source_divergence(monkeypatch):
    patch_fake_pyspark(monkeypatch)
    score = np.linspace(-3, 3, 180)
    target = np.r_[np.tile([0, 1], 30), np.ones(120, dtype=int)]
    spark_df = ValidatingFakeSparkDataFrame(
        pd.DataFrame({"score": score, "target": target}),
        sample_mode="head",
    )
    binner = RiskBands(strategy="supervised", max_bins=3, min_event_rate_diff=0.0, sample_size=60)

    binner.fit(spark_df, target="target", column="score", validate=True)

    assert binner.validation_report_["sample_representativeness"]["status"] in {"warning", "critical"}
    assert binner.validation_report_["summary"]["possible_sample_size_issue"] is True
