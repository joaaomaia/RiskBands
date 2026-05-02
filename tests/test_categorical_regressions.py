import numpy as np
import pandas as pd

from riskbands import Binner
from riskbands.strategies.categorical import CategoricalBinning


def make_categorical_credit_frame(n=240, seed=42):
    rng = np.random.default_rng(seed)

    grade = rng.choice(
        ["A", "B", "C", "D", "RARE_X", "RARE_Y"],
        size=n,
        p=[0.30, 0.25, 0.20, 0.18, 0.04, 0.03],
    )
    score = rng.normal(loc=0.0, scale=1.0, size=n)

    grade_risk = {
        "A": 0.06,
        "B": 0.10,
        "C": 0.18,
        "D": 0.30,
        "RARE_X": 0.35,
        "RARE_Y": 0.40,
    }
    proba = np.array([grade_risk[g] for g in grade]) + 0.05 * (score > 0)
    proba = np.clip(proba, 0.01, 0.95)
    target = (rng.random(n) < proba).astype(int)

    df = pd.DataFrame(
        {
            "score": score,
            "grade": grade,
            "target": target,
        },
        index=pd.Index(range(1000, 1000 + n), name="custom_id"),
    )

    missing_idx = df.sample(8, random_state=seed).index
    df.loc[missing_idx, "grade"] = None

    return df


def test_categorical_binning_transform_preserves_index_and_column_name():
    df = make_categorical_credit_frame()
    cat_binner = CategoricalBinning(max_bins=4)

    cat_binner.fit(df[["grade"]], df["target"])
    X_new = pd.DataFrame(
        {"grade": ["A", "B", "C", None, "UNKNOWN_NEW_CATEGORY"]},
        index=pd.Index([501, 503, 509, 521, 541], name="application_id"),
    )

    transformed = cat_binner.transform(X_new)

    assert isinstance(transformed, pd.DataFrame)
    assert transformed.index.equals(X_new.index)
    assert list(transformed.columns) == ["grade"]
    assert len(transformed) == len(X_new)
    assert not transformed["grade"].isna().all()


def test_categorical_binning_applies_learned_rare_mapping_on_transform():
    df = make_categorical_credit_frame()
    cat_binner = CategoricalBinning(rare_threshold=0.08, max_bins=4)

    cat_binner.fit(df[["grade"]], df["target"])
    X_new = pd.DataFrame(
        {"grade": ["RARE_X", "RARE_Y", "A", "UNKNOWN_NEW_CATEGORY", None]},
        index=[501, 502, 503, 504, 505],
    )

    transformed = cat_binner.transform(X_new)

    assert transformed.index.equals(X_new.index)
    assert list(transformed.columns) == ["grade"]
    assert len(transformed) == len(X_new)
    assert transformed["grade"].iloc[0] == transformed["grade"].iloc[1]


def test_binner_fit_transform_mixed_numeric_and_categorical_frame():
    df = make_categorical_credit_frame()
    binner = Binner(
        strategy="supervised",
        max_bins=4,
        min_event_rate_diff=0.0,
        force_categorical=["grade"],
    )

    binner.fit(df, y="target", columns=["score", "grade"])
    transformed = binner.transform(df[["score", "grade"]])

    assert transformed.index.equals(df.index)
    assert list(transformed.columns) == ["score", "grade"]

    table = binner.binning_table()
    assert set(table["variable"]) == {"score", "grade"}


def test_binner_fit_transform_matches_fit_then_transform_for_categorical_feature():
    df = make_categorical_credit_frame()
    kwargs = {
        "strategy": "supervised",
        "max_bins": 4,
        "min_event_rate_diff": 0.0,
        "force_categorical": ["grade"],
    }

    b1 = Binner(**kwargs)
    out_fit_transform = b1.fit_transform(
        df,
        y="target",
        column="grade",
        return_type="dataframe",
    )

    b2 = Binner(**kwargs)
    b2.fit(df, y="target", column="grade")
    out_separate = b2.transform(df[["grade"]], return_type="dataframe")

    assert out_fit_transform.index.equals(df.index)
    assert list(out_fit_transform.columns) == ["grade"]
    assert out_separate.index.equals(df.index)
    assert list(out_separate.columns) == ["grade"]
    pd.testing.assert_frame_equal(out_fit_transform, out_separate)


def test_binner_categorical_transform_handles_unknown_and_missing_values():
    df = make_categorical_credit_frame()
    binner = Binner(
        strategy="supervised",
        max_bins=4,
        min_event_rate_diff=0.0,
        force_categorical=["grade"],
    )

    binner.fit(df, y="target", column="grade")
    X_new = pd.DataFrame(
        {"grade": ["A", "RARE_X", "UNKNOWN_NEW_CATEGORY", None]},
        index=pd.Index([9001, 9002, 9003, 9004], name="application_id"),
    )

    transformed = binner.transform(X_new, return_type="dataframe")

    assert transformed.index.equals(X_new.index)
    assert list(transformed.columns) == ["grade"]
    assert len(transformed) == len(X_new)
