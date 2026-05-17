import json

import numpy as np
import pandas as pd

from riskbands import RiskBands
from riskbands.reporting import load_bundle_metadata
from riskbands.utils import dataframe_backend


class FakeSparkDataFrame:
    def __init__(self, pdf: pd.DataFrame, ops: dict | None = None):
        self._pdf = pdf.copy()
        self.ops = ops if ops is not None else {"selects": [], "samples": [], "limits": []}

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
        self.ops["samples"].append({"fraction": fraction, "seed": seed})
        n = min(len(self._pdf), int(np.ceil(len(self._pdf) * float(fraction))))
        return FakeSparkDataFrame(self._pdf.sample(n=n, random_state=seed), self.ops)

    def limit(self, n):
        self.ops["limits"].append(n)
        return FakeSparkDataFrame(self._pdf.head(n), self.ops)

    def toPandas(self):
        return self._pdf.copy()


def make_frame(n=240, seed=91):
    rng = np.random.default_rng(seed)
    score = np.linspace(-3, 3, n)
    proba = 1 / (1 + np.exp(-2 * score))
    target = (rng.random(n) < proba).astype(int)
    return pd.DataFrame({"score": score, "target": target})


def fit_binner(df=None, **kwargs):
    df = make_frame() if df is None else df
    binner = RiskBands(strategy="supervised", max_bins=4, min_event_rate_diff=0.0, **kwargs)
    binner.fit(df, y="target", column="score")
    return binner, df


def test_fit_profile_is_created_for_pandas_fit():
    binner, df = fit_binner()

    assert hasattr(binner, "fit_profile_")
    assert not binner.fit_profile_.empty
    assert set(
        [
            "variable",
            "bin_id",
            "bin_label",
            "bin_order",
            "n",
            "events",
            "non_events",
            "event_rate",
            "event_rate_std_error",
            "event_rate_ci_lower",
            "event_rate_ci_upper",
            "share",
            "woe",
            "iv_component",
            "is_missing_bin",
            "is_special_bin",
            "is_regular_bin",
        ]
    ).issubset(binner.fit_profile_.columns)
    assert int(binner.fit_profile_["n"].sum()) == len(df)


def test_fit_profile_has_one_row_per_observed_fit_bin():
    binner, df = fit_binner()
    transformed = binner.transform(df[["score"]])

    assert len(binner.fit_profile_) == transformed["score"].nunique(dropna=False)


def test_fit_profile_event_rate_is_correct():
    binner, df = fit_binner()
    transformed = binner.transform(df[["score"]])
    profile_row = binner.fit_profile_.iloc[0]
    mask = transformed["score"].astype(str) == str(profile_row["bin_label"])
    expected_events = df.loc[mask, "target"].sum()
    expected_n = mask.sum()

    assert profile_row["events"] == expected_events
    assert profile_row["n"] == expected_n
    assert profile_row["event_rate"] == expected_events / expected_n


def test_fit_profile_handles_zero_and_full_event_bins():
    x = np.arange(90)
    df_zero = pd.DataFrame({"score": x, "target": np.zeros(90, dtype=int)})
    df_one = pd.DataFrame({"score": x, "target": np.ones(90, dtype=int)})

    for df in (df_zero, df_one):
        binner = RiskBands(strategy="unsupervised", max_bins=3)
        binner.fit(df, y="target", column="score")
        assert not binner.fit_profile_.empty
        assert binner.fit_profile_["event_rate"].notna().all()
        assert np.isfinite(binner.fit_profile_["woe"]).all()


def test_fit_profile_is_created_for_sampled_pyspark_fit(monkeypatch):
    monkeypatch.setattr(dataframe_backend, "_pyspark_dataframe_class", lambda: FakeSparkDataFrame)
    spark_df = FakeSparkDataFrame(make_frame(n=180))
    binner = RiskBands(strategy="supervised", max_bins=3, min_event_rate_diff=0.0, sample_size=50)

    binner.fit(spark_df, target="target", column="score")

    assert not binner.fit_profile_.empty
    assert int(binner.fit_profile_["n"].sum()) == binner.sampling_metadata_["n_rows_fit"]


def test_bundle_exports_and_loads_fit_profile(tmp_path):
    binner, _ = fit_binner()
    bundle_dir = tmp_path / "bundle"

    binner.export_bundle(bundle_dir)

    manifest = json.loads((bundle_dir / "metadata.json").read_text(encoding="utf-8"))
    loaded = load_bundle_metadata(bundle_dir)

    assert "fit_profile" in manifest
    assert len(manifest["fit_profile"]) == len(binner.fit_profile_)
    assert loaded["fit_profile"] == manifest["fit_profile"]
