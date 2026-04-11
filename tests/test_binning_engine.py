import pandas as pd
import numpy as np
from riskbands import Binner

def test_basic_fit_transform():
    rng = np.random.default_rng(42)
    df = pd.DataFrame({
        "x1": rng.normal(size=500),
        "x2": rng.uniform(-2, 2, size=500),
    })
    y = (df["x1"] + rng.normal(scale=0.5, size=500) > 0).astype(int)

    binner = Binner(strategy="supervised",
                        max_bins=5,
                        min_event_rate_diff=0.01)
    Xt = binner.fit_transform(df, y)
    # Deve manter shape e nÃ£o conter NaNs
    assert Xt.shape == df.shape
    assert not Xt.isna().any().any()
    # IV calculado
    assert hasattr(binner, "iv_")
    assert binner.iv_ > 0


