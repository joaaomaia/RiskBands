---
title: Quickstart
description: "Ajuste seu primeiro RiskBands com a API mais amigavel do projeto e inspecione score, auditoria, export e plots em poucos passos."
---

## O fluxo recomendado hoje

Para um usuario novo, o caminho mais simples e completo e:

1. criar um `RiskBands`
2. ajustar com `fit(df, y="target", column="score", time_col="month")`
3. olhar `summary()`
4. abrir `score_table()` e `audit_table()`
5. exportar os artefatos auditaveis
6. usar os plots publicos para leitura temporal

```python
import numpy as np
import pandas as pd

from riskbands import RiskBands

rng = np.random.default_rng(0)
n = 800

df = pd.DataFrame({"score": rng.normal(size=n)})
df["month"] = rng.choice([202301, 202302, 202303, 202304], size=n)

proba = 0.20 + 0.15 * df["score"] + 0.02 * (df["month"] - 202301)
proba = np.clip(proba, 0.01, 0.99)
df["target"] = (rng.random(n) < proba).astype(int)

binner = RiskBands(
    strategy="supervised",
    max_n_bins=5,
    check_stability=True,
    missing_policy="standard",
    score_strategy="stable",
    normalization_strategy="absolute",
    woe_shrinkage_strength=35.0,
)

binner.fit(df, y="target", column="score", time_col="month")

score_bins = binner.transform(df["score"])
summary = binner.summary()
score_table = binner.score_table()
audit_table = binner.audit_table()

binner.export_binnings_json("artifacts/riskbands_binnings.json")
binner.export_bundle("artifacts/quickstart_run")

binner.plot_bad_rate_over_time(df, y="target", column="score", time_col="month")
binner.plot_bad_rate_heatmap(df, y="target", column="score", time_col="month")
binner.plot_bin_share_over_time(df, y="target", column="score", time_col="month")
binner.plot_score_components(column="score")
```

## Missing values

O default `missing_policy="standard"` preserva o comportamento atual. Quando
voce precisa auditar missing values explicitamente, use
`missing_policy="separate_bin"`. Quando missing values devem ser bloqueados
antes do binning, use `missing_policy="forbid"`.

Quando missing deve continuar auditavel, mas ser roteado para um bin regular,
use `missing_policy="merge"` com `missing_merge_criterion="nearest_event_rate"`
ou `missing_merge_criterion="nearest_woe"`.

Essas politicas nao fazem imputacao opaca. Em merge, a regra e aprendida no
`fit` e reutilizada no `transform`, sem recalcular destino com a base de
aplicacao.

Para exemplos pandas e PySpark completos, veja [Missing policy](../missing-policy/).

## O que olhar primeiro

### `summary()`

Melhor primeira parada depois do ajuste: bins, IV, estrategia de score e alertas
temporais.

### `score_table()`

Leitura curta para explicar score final, score de comparacao, direcao do
objective, pesos e componentes mais relevantes.

### `audit_table()`

Visao consolidada para revisao auditavel: cortes finais, score, cobertura, bins
raros, reversoes e rationale resumido.

## Quando usar `stable`

Para um novo usuario, `stable` costuma ser a melhor estrategia publica para
comecar quando existe coluna temporal, estabilidade importa e voce quer
equilibrar separacao e robustez.

Se voce precisa reproduzir comportamento historico ou comparar com a abordagem
anterior, use `standard`.

## Proximos passos

- [Auditoria e plots](../audit-and-plots/)
- [Missing policy](../missing-policy/)
- [Outputs e diagnostico](../outputs/)
- [Score e estrategias](../score-strategy/)
- [Exemplos](../examples/)
