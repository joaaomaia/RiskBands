import json
from unittest.mock import patch

import matplotlib
import numpy as np
import pandas as pd

from riskbands import Binner
from riskbands.reporting import save_binner_report

matplotlib.use("Agg")


def _make_temporal_dataset(seed: int = 7):
    rng = np.random.default_rng(seed)
    n = 240
    month = np.repeat([202301, 202302, 202303, 202304], n // 4)
    x = rng.normal(size=n)
    drift = (month - month.min()) / 1000
    y = (x + drift + rng.normal(scale=0.35, size=n) > 0).astype(int)
    X = pd.DataFrame({"x": x, "month": month})
    return X, pd.Series(y)


def test_stability_over_time_excludes_time_col_without_optuna():
    X, y = _make_temporal_dataset()
    binner = Binner(strategy="supervised", check_stability=True)
    binner.fit(X, y, time_col="month")

    pivot = binner.stability_over_time(X, y, time_col="month")

    assert set(binner.bin_summary["variable"]) == {"x"}
    assert set(pivot.index.get_level_values("variable")) == {"x"}
    assert list(pivot.columns) == [202301, 202302, 202303, 202304]


def test_plot_event_rate_stability_smoke():
    X, y = _make_temporal_dataset()
    binner = Binner(strategy="supervised", check_stability=True)
    binner.fit(X, y, time_col="month")
    pivot = binner.stability_over_time(X, y, time_col="month")

    with patch("matplotlib.pyplot.show"):
        figures = binner.plot_event_rate_stability(pivot)

    assert len(figures) == 1


def test_save_json_report_includes_temporal_pivot(tmp_path):
    X, y = _make_temporal_dataset()
    binner = Binner(strategy="supervised", check_stability=True)
    binner.fit(X, y, time_col="month")
    binner.stability_over_time(X, y, time_col="month")

    report_path = tmp_path / "report.json"
    save_binner_report(binner, report_path)

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["iv"] >= 0
    assert "pivot_event_rate" in payload


def test_optuna_temporal_smoke_handles_sparse_vintages():
    X, y = _make_temporal_dataset()
    mask = ~((X["month"] == 202304) & (X["x"] > 1.0))
    sparse = X.loc[mask].reset_index(drop=True)
    y_sparse = y.loc[mask].reset_index(drop=True)

    binner = Binner(
        strategy="supervised",
        check_stability=True,
        use_optuna=True,
        strategy_kwargs={"n_trials": 2},
    )
    binner.fit(sparse, y_sparse, time_col="month")

    pivot = binner.stability_over_time(sparse, y_sparse, time_col="month")
    assert not pivot.empty
    assert set(binner.best_params_.keys()) == {"x"}


