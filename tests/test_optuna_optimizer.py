import pandas as pd
import numpy as np
from riskbands.optuna_optimizer import optimize_bins

def test_optuna_runs_quickly():
    rng = np.random.default_rng(3)
    X = pd.DataFrame({"x": rng.normal(size=120)})
    y = (X["x"] > 0).astype(int)
    best, binner = optimize_bins(X, y, n_trials=5, strategy="supervised")
    assert 3 <= best["max_bins"] <= 10
    assert isinstance(binner.iv_, float)


