"""Example demonstrating temporal stability with NASABinning."""

import numpy as np
import pandas as pd

from nasabinning import NASABinner
from nasabinning.temporal_stability import ks_over_time, temporal_separability_score


# synthetic dataset -------------------------------------------------------
rng = np.random.default_rng(0)
n = 800

X = pd.DataFrame({"x": rng.normal(size=n)})
X["month"] = rng.choice([202301, 202302, 202303, 202304], size=n)

proba = 0.20 + 0.15 * X["x"] + 0.02 * (X["month"] - 202301)
proba = np.clip(proba, 0.01, 0.99)
y = pd.Series((rng.random(n) < proba).astype(int), name="target")


# fit NASABinner using Optuna to maximize temporal separability ----------
binner = NASABinner(
    strategy="supervised",
    check_stability=True,
    use_optuna=True,
    time_col="month",
    strategy_kwargs={"n_trials": 10},
)

binner.fit(X, y, time_col="month")


# stability metrics -------------------------------------------------------
pivot = binner.stability_over_time(X, y, time_col="month")
diagnostics = binner.temporal_bin_diagnostics(
    X,
    y,
    time_col="month",
    dataset_name="train",
)
summary = binner.temporal_variable_summary(diagnostics=diagnostics, time_col="month")
ks = ks_over_time(pivot)

bins = binner.transform(X)["x"]
sep = temporal_separability_score(
    pd.DataFrame({"bin": bins, "target": y, "time": X["month"]}),
    "x",
    "bin",
    "target",
    "time",
)

print(f"Temporal separability: {sep:.3f}")
print(f"IV: {binner.iv_:.3f}")
print(f"KS over time: {ks:.3f}")
print("Best params:", binner.best_params_)
print(diagnostics.head())
print(summary[["variable", "temporal_score", "alert_flags"]])


# optional export ---------------------------------------------------------
binner.plot_event_rate_stability(pivot)
binner.save_report("reports/temporal_stability_example.xlsx")
