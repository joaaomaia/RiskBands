import pandas as pd
import numpy as np
from riskbands import Binner
from riskbands.reporting import save_binner_report
from pathlib import Path
import tempfile

def test_save_excel(tmp_path: Path):
    rng = np.random.default_rng(4)
    X = pd.DataFrame({"x": rng.normal(size=100)})
    y = (X["x"] > 0).astype(int)
    binner = Binner(strategy="supervised").fit(X, y)
    file_path = tmp_path / "report.xlsx"
    save_binner_report(binner, file_path)
    assert file_path.exists() and file_path.stat().st_size > 0


