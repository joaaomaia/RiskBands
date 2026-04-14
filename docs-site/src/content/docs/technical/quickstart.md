---
title: Quickstart
description: "Ajuste seu primeiro Binner com uma API mais pandas-first, inspecione o score e abra o diagnóstico temporal quando necessário."
---

## Fluxo mínimo

O fluxo recomendado agora é curto e familiar para quem já usa pandas e sklearn:

1. ajustar um `Binner`
2. transformar a coluna quando quiser
3. inspecionar `summary()` e `score_details()`
4. abrir `diagnostics()` ou `report()` quando precisar aprofundar

```python
import numpy as np
import pandas as pd

from riskbands import Binner

rng = np.random.default_rng(0)
n = 800

df = pd.DataFrame({"score": rng.normal(size=n)})
df["month"] = rng.choice([202301, 202302, 202303, 202304], size=n)

proba = 0.20 + 0.15 * df["score"] + 0.02 * (df["month"] - 202301)
proba = np.clip(proba, 0.01, 0.99)
df["target"] = (rng.random(n) < proba).astype(int)

binner = Binner(
    strategy="supervised",
    max_n_bins=5,
    check_stability=True,
    monotonic="ascending",
    min_event_rate_diff=0.03,
    score_strategy="generalization_v1",
)

binner.fit(df, y="target", column="score", time_col="month")
score_bins = binner.transform(df["score"])
summary = binner.summary()
score_details = binner.score_details()
diagnostics = binner.diagnostics(kind="bin")
audit = binner.report()
```

## O que olhar primeiro

### `summary()`

Use `summary()` para uma leitura curta por variável:

- IV
- score temporal
- score final do objective
- cobertura mínima
- contagem de bins raros
- reversões de ranking

É a melhor primeira parada depois do `fit`.

### `score_details()`

Use `score_details()` quando a pergunta for:

- qual foi o score final?
- qual estratégia está ativa: `legacy` ou `generalization_v1`?
- quais componentes e pesos entraram na decisão?

### `diagnostics()`

Use `diagnostics(kind="bin")` para abrir a granularidade de variável x bin x período sem precisar lembrar do caminho interno completo.

### `report()`

Use `report()` quando você precisar de uma tabela única que consolide:

- cortes
- IV e KS
- score temporal
- score objetivo
- penalizações
- resumo textual do racional

## Compatibilidade com o objective novo

O quickstart mais amigável não remove nenhuma capacidade do core pós-`v1.1.0`.

Você continua controlando normalmente:

- `score_strategy`
- `score_weights`
- `normalization_strategy`
- `woe_shrinkage_strength`
- `objective_kwargs`

## Próximos passos

- [Visão geral da API](../api-overview/)
- [Exemplos](../examples/)
- [Benchmark PD vintage](../../methodology/pd-vintage-benchmark/)
