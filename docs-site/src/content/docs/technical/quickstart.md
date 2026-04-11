---
title: Quickstart
description: "Ajuste seu primeiro Binner, inspecione o comportamento temporal e gere uma leitura auditável."
---

## Fluxo mínimo

O fluxo central do RiskBands foi pensado para ser curto:

1. ajustar um `Binner`
2. inspecionar o comportamento temporal
3. resumir a estabilidade da variável
4. gerar uma visão auditável do candidato

```python
import numpy as np
import pandas as pd

from riskbands import Binner

rng = np.random.default_rng(0)
n = 800

X = pd.DataFrame({"score": rng.normal(size=n)})
X["month"] = rng.choice([202301, 202302, 202303, 202304], size=n)

proba = 0.20 + 0.15 * X["score"] + 0.02 * (X["month"] - 202301)
proba = np.clip(proba, 0.01, 0.99)
y = pd.Series((rng.random(n) < proba).astype(int), name="target")

binner = Binner(
    strategy="supervised",
    check_stability=True,
    monotonic="ascending",
    min_event_rate_diff=0.03,
)

binner.fit(X, y, time_col="month")
diagnostics = binner.temporal_bin_diagnostics(
    X,
    y,
    time_col="month",
    dataset_name="train",
)
summary = binner.temporal_variable_summary(
    diagnostics=diagnostics,
    time_col="month",
)
audit = binner.variable_audit_report(
    X,
    y,
    time_col="month",
    dataset_name="train",
)
```

## O que olhar primeiro

### `summary`

Use `temporal_variable_summary(...)` para obter uma leitura por variável com indicadores como:

- `temporal_score`
- cobertura mínima
- contagem de bins raros
- volatilidade de event rate, WoE e participação do bin
- reversões de ordenação
- quebras de monotonicidade

É uma boa porta de entrada para responder: "a variável ainda parece saudável quando eu abro por safra?"

### `audit`

Use `variable_audit_report(...)` quando você precisar de uma tabela única que consolide:

- cortes
- IV e KS
- score temporal
- score objetivo
- penalizações
- resumo textual do racional

Essa é a camada que ajuda a transformar diagnóstico em decisão explicável.

## Quando sair do candidato único

Se a sua pergunta já não é mais "quais são os cortes?" e sim "qual candidato eu deveria confiar?", o próximo passo natural é o `BinComparator`.

É nesse ponto que o RiskBands fica especialmente útil para trabalho de crédito com champion challenger, benchmark e escolha final por trade-off.

- Vá para [Visão geral da API](/technical/api-overview/)
- Ou pule direto para [Benchmark PD vintage](/methodology/pd-vintage-benchmark/)
