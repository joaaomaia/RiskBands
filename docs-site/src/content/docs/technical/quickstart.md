---
title: Quickstart
description: "Ajuste seu primeiro Binner com a API mais amigável do RiskBands e entenda os outputs principais em poucos passos."
---

## O fluxo recomendado hoje

Para um usuário novo, o caminho mais fácil é:

1. criar um `Binner`
2. ajustar com `fit(df, y="target", column="score", time_col="month")`
3. olhar `summary()`
4. abrir `score_details()` ou `diagnostics()` quando precisar aprofundar

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
    score_strategy="stable",
)

binner.fit(df, y="target", column="score", time_col="month")
score_bins = binner.transform(df["score"])
summary = binner.summary()
score_details = binner.score_details()
diagnostics = binner.diagnostics(kind="bin")
```

## Por que esse fluxo é mais amigável

Ele segue convenções familiares:

- `fit(...)`
- `transform(...)`
- `fit_transform(...)`
- `get_params()` / `set_params(...)`
- `DataFrame` e `Series` do pandas como primeira opção

Também evita exigir que você memorize estruturas internas logo no começo.

## O que olhar primeiro

### `summary()`

É a melhor primeira parada após o ajuste.

Use quando quiser responder rapidamente:

- quantos bins ficaram?
- qual foi o IV?
- qual estratégia de score está ativa?
- qual foi o score final?
- existem alertas temporais importantes?

### `score_details()`

Use quando a pergunta for:

- por que esse score saiu assim?
- o que entrou no objective?
- quais pesos foram usados?
- qual normalização está ativa?
- qual `woe_shrinkage_strength` foi aplicado?

### `diagnostics()`

Use `diagnostics(kind="bin")` para abrir a granularidade por variável x bin x período.

Use `diagnostics(kind="variable")` para um resumo temporal por variável.

## Quando usar `stable`

Para um novo usuário, `stable` costuma ser a melhor estratégia pública para começar quando:

- existe coluna temporal
- estabilidade importa de verdade
- você quer equilibrar separação e robustez

Se você precisa reproduzir um comportamento mais histórico ou comparar com a abordagem anterior, use `legacy`.

## Próximos passos

- [Score e estratégias](../score-strategy/)
- [Outputs e diagnóstico](../outputs/)
- [Optuna](../optuna/)
