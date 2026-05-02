import re

import numpy as np
import pandas as pd
import pytest

from riskbands import Binner
from riskbands.utils.dtypes import search_dtypes


def make_low_cardinality_numeric_frame(n=160, seed=123):
    rng = np.random.default_rng(seed)
    risk_bucket = rng.choice([1, 2, 3], size=n, p=[0.45, 0.35, 0.20])
    noise = rng.normal(size=n)
    proba = (
        0.05
        + 0.12 * (risk_bucket == 2)
        + 0.28 * (risk_bucket == 3)
        + 0.03 * (noise > 0)
    )
    proba = np.clip(proba, 0.01, 0.95)
    target = (rng.random(n) < proba).astype(int)
    return pd.DataFrame(
        {
            "risk_bucket": risk_bucket,
            "noise": noise,
            "target": target,
        },
        index=pd.Index(range(5000, 5000 + n), name="application_id"),
    )


def test_search_dtypes_respects_force_numeric_override():
    df = make_low_cardinality_numeric_frame()
    df["risk_bucket"] = df["risk_bucket"].astype(object)

    base_num_cols, base_cat_cols = search_dtypes(df, target_col="target", verbose=False)
    assert "risk_bucket" not in base_num_cols
    assert "risk_bucket" in base_cat_cols

    num_cols, cat_cols = search_dtypes(
        df,
        target_col="target",
        force_numeric=["risk_bucket"],
        verbose=False,
    )

    assert "risk_bucket" in num_cols
    assert "risk_bucket" not in cat_cols


def test_binner_force_numeric_keeps_low_cardinality_feature_numeric():
    df = make_low_cardinality_numeric_frame()
    df["risk_bucket"] = df["risk_bucket"].astype(object)
    binner = Binner(
        strategy="supervised",
        max_bins=4,
        min_event_rate_diff=0.0,
        force_numeric=["risk_bucket"],
    )

    binner.fit(df, y="target", column="risk_bucket")

    assert "risk_bucket" in binner.numeric_cols_
    assert "risk_bucket" not in binner.cat_cols_

    schema = binner.describe_schema()
    row = schema.loc[schema["col"] == "risk_bucket"].iloc[0]
    assert row["tipo"] == "numeric"

    transformed = binner.transform(df[["risk_bucket"]], return_type="dataframe")
    assert transformed.index.equals(df.index)
    assert list(transformed.columns) == ["risk_bucket"]


def test_binner_force_categorical_still_overrides_numeric_dtype():
    df = make_low_cardinality_numeric_frame()
    binner = Binner(
        strategy="supervised",
        max_bins=4,
        min_event_rate_diff=0.0,
        force_categorical=["risk_bucket"],
    )

    binner.fit(df, y="target", column="risk_bucket")
    transformed = binner.transform(df[["risk_bucket"]], return_type="dataframe")

    assert "risk_bucket" in binner.cat_cols_
    assert "risk_bucket" not in binner.numeric_cols_
    assert transformed.index.equals(df.index)
    assert list(transformed.columns) == ["risk_bucket"]


def test_binner_rejects_force_numeric_and_force_categorical_conflict():
    df = make_low_cardinality_numeric_frame()
    pattern = re.compile(
        r"force_numeric.*force_categorical.*risk_bucket"
        r"|force_categorical.*force_numeric.*risk_bucket"
    )

    with pytest.raises(ValueError, match=pattern):
        Binner(
            force_numeric=["risk_bucket"],
            force_categorical=["risk_bucket"],
        ).fit(df, y="target", column="risk_bucket")


def test_binner_force_numeric_accepts_numeric_strings():
    df = make_low_cardinality_numeric_frame()
    df["risk_bucket"] = df["risk_bucket"].astype(str)
    binner = Binner(
        strategy="supervised",
        max_bins=4,
        min_event_rate_diff=0.0,
        force_numeric=["risk_bucket"],
    )

    binner.fit(df, y="target", column="risk_bucket")
    transformed = binner.transform(df[["risk_bucket"]], return_type="dataframe")

    assert "risk_bucket" in binner.numeric_cols_
    assert "risk_bucket" not in binner.cat_cols_
    assert transformed.index.equals(df.index)
    assert list(transformed.columns) == ["risk_bucket"]


def test_binner_force_numeric_rejects_non_numeric_strings_with_clear_error():
    df = pd.DataFrame(
        {
            "bad_numeric": ["A", "B", "C", "A", "B", "C", "A", "B"],
            "target": [0, 1, 0, 1, 0, 1, 0, 1],
        }
    )

    with pytest.raises(ValueError, match="force_numeric|numeric|bad_numeric"):
        Binner(force_numeric=["bad_numeric"]).fit(df, y="target", column="bad_numeric")


def test_binner_force_numeric_mixed_frame_preserves_column_order_and_schema():
    df = make_low_cardinality_numeric_frame()
    df["risk_bucket"] = df["risk_bucket"].astype(object)
    binner = Binner(
        strategy="supervised",
        max_bins=4,
        min_event_rate_diff=0.0,
        force_numeric=["risk_bucket"],
    )

    binner.fit(df, y="target", columns=["risk_bucket", "noise"])
    transformed = binner.transform(df[["risk_bucket", "noise"]], return_type="dataframe")
    schema = binner.describe_schema().set_index("col")

    assert list(transformed.columns) == ["risk_bucket", "noise"]
    assert schema.loc["risk_bucket", "tipo"] == "numeric"
    assert schema.loc["noise", "tipo"] == "numeric"


def test_binner_force_numeric_is_respected_with_optuna():
    df = make_low_cardinality_numeric_frame(n=120)
    df["risk_bucket"] = df["risk_bucket"].astype(str)
    binner = Binner(
        strategy="supervised",
        use_optuna=True,
        force_numeric=["risk_bucket"],
        strategy_kwargs={"n_trials": 2, "sampler_seed": 123},
    )

    binner.fit(df, y="target", column="risk_bucket")

    assert "risk_bucket" in binner.numeric_cols_
    assert "risk_bucket" not in binner.cat_cols_
    fitted_binner = getattr(binner, "_per_feature_binners", {}).get("risk_bucket")
    if fitted_binner is not None:
        assert "risk_bucket" in fitted_binner.numeric_cols_
        assert "risk_bucket" not in fitted_binner.cat_cols_
