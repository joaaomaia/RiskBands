import numpy as np
import pandas as pd

from riskbands.strategies.unsupervised import UnsupervisedBinning


def test_unsupervised_multi_column():
    rng = np.random.default_rng(0)
    X = pd.DataFrame({
        "a": rng.normal(size=100),
        "b": rng.uniform(size=100)
    })
    ub = UnsupervisedBinning(method="kmeans", n_bins=4)
    Xt = ub.fit(X).transform(X)
    assert Xt.shape == X.shape
    assert Xt.nunique().max() <= 4


