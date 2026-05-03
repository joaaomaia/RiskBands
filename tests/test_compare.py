import numpy as np
import pandas as pd

from riskbands.compare import BinComparator


def test_compare_two_strategies():
    rng = np.random.default_rng(1)
    X = pd.DataFrame({"x": rng.normal(size=200)})
    y = (X["x"] + rng.normal(scale=0.35, size=200) > 0).astype(int)
    configs = [
        dict(strategy="supervised", max_bins=5, name="sup"),
        dict(strategy="unsupervised", method="quantile", n_bins=5, name="unsup"),
    ]
    cmp = BinComparator(configs)
    res = cmp.fit_compare(X, y)
    assert {"sup", "unsup"} <= set(res.index)
    assert res.loc["sup", "iv"] > 0            # supervised tem IV calculado


