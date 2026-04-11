"""
metrics.py
MÃ©tricas clÃ¡ssicas de modelagem de risco de crÃ©dito.
IV: Information Value
PSI: Population Stability Index
"""

import numpy as np
import pandas as pd


def iv(bin_tbl: pd.DataFrame,
       col_event: str = "event",
       col_non_event: str = "non_event") -> float:
    """Calcula Information Value a partir de tabela de bins."""
    evt = bin_tbl[col_event].values
    non = bin_tbl[col_non_event].values
    evt_prop = evt / evt.sum()
    non_prop = non / non.sum()
    woe = np.log(np.clip(evt_prop, 1e-9, None) /
                 np.clip(non_prop, 1e-9, None))
    return float(np.sum((evt_prop - non_prop) * woe))


def psi(df_bins: pd.DataFrame,
        by: str | None = None,
        col_event_rate: str = "event_rate") -> float:
    """
    PSI simples: compara distribuiÃ§Ã£o de event-rate entre dois subconjuntos.
    Se `by` Ã© None, espera colunas 'expected' e 'actual'.
    Se `by` Ã© str, assume df com mÃºltiplas linhas por bin (ex: safras) e
    calcula PSI entre a primeira e a Ãºltima categoria.
    """
    if by is None:
        exp = df_bins["expected"].values
        act = df_bins["actual"].values
    else:
        cats = df_bins[by].unique()
        if len(cats) < 2:
            return 0.0
        first, last = cats.min(), cats.max()
        exp = df_bins.loc[df_bins[by] == first, col_event_rate].values
        act = df_bins.loc[df_bins[by] == last,  col_event_rate].values

    exp = np.clip(exp, 1e-9, None)
    act = np.clip(act, 1e-9, None)
    return float(np.sum((act - exp) * np.log(act / exp)))


