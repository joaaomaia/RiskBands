---
title: Quickstart
description: "Ajuste seu primeiro Binner com a API mais amigável do RiskBands e inspecione score, auditoria, export e plots em poucos passos."
---

## O fluxo recomendado hoje

Para um usuário novo, o caminho mais simples e completo é:

1. criar um `Binner`
2. ajustar com `fit(df, y="target", column="score", time_col="month")`
3. olhar `summary()`
4. abrir `score_table()` e `audit_table()`
5. exportar os artefatos auditáveis
6. usar os plots públicos para leitura temporal

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

## Por que esse fluxo é mais amigável

Ele segue convenções familiares:

- `fit(...)`
- `transform(...)`
- `fit_transform(...)`
- `DataFrame` e `Series` do pandas como primeira opção
- tabelas curtas para notebook antes de abrir o detalhe completo

Também evita exigir que você monte pivots, bundles ou dicionários internos logo no começo.

## O que olhar primeiro

### `summary()`

É a melhor primeira parada depois do ajuste.

Use quando quiser responder rapidamente:

- quantos bins ficaram?
- qual foi o IV?
- qual estratégia de score está ativa?
- existem alertas temporais relevantes?

### `score_table()`

É a leitura mais curta para explicar o objective.

Ela ajuda a enxergar:

- score final
- score de comparação
- direção do objective
- pesos usados
- componentes e penalidades mais relevantes

### `audit_table()`

É a visão consolidada para revisão auditável.

Ela junta:

- cortes finais
- score
- cobertura
- bins raros
- reversões
- rationale resumido

## Quando usar `stable`

Para um novo usuário, `stable` costuma ser a melhor estratégia pública para começar quando:

- existe coluna temporal
- estabilidade importa de verdade
- você quer equilibrar separação e robustez

Se você precisa reproduzir um comportamento mais histórico ou comparar com a abordagem anterior, use `legacy`.

## Próximos passos

- [Auditoria e plots](../audit-and-plots/)
- [Outputs e diagnóstico](../outputs/)
- [Score e estratégias](../score-strategy/)
- [Exemplos](../examples/)
