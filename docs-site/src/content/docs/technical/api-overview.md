---
title: "Visão geral da API"
description: "Mapa da superfície principal do pacote, com foco na camada pública mais amigável construída sobre o core de score pós-v1.1.0."
---

## Superfície pública principal

```python
from riskbands import Binner, BinComparator
from riskbands.temporal_stability import (
    ks_over_time,
    psi_over_time,
    temporal_separability_score,
)
```

## O que mudou na ergonomia

Sem mexer agressivamente no core, a API pública do `Binner` agora ficou mais próxima de padrões familiares de sklearn e pandas:

- `fit(df, y="target", column="score")`
- `fit(df["score"], y=df["target"])`
- `transform(df)` ou `transform(df["score"])`
- `fit_transform(...)`
- `summary()`
- `report()`
- `score_details()`
- `diagnostics()`
- `binning_table()`
- `plot_stability()`
- `get_params()` e `set_params(...)`

Também foram adicionados aliases mais amigáveis para configuração:

- `max_n_bins` como alias de `max_bins`
- `monotonic_trend` como alias de `monotonic`

## Blocos centrais

| Componente | Papel no fluxo | Por que importa |
| --- | --- | --- |
| `Binner` | Porta de entrada principal | Ajusta, transforma, resume e expõe score/diagnóstico em uma superfície mais amigável |
| `summary()` | Resumo curto pós-fit | Ajuda a entender rapidamente bins, IV e score |
| `score_details()` | Detalhamento do objective | Expõe score final, componentes, normalização e pesos |
| `diagnostics()` | Leitura temporal rápida | Evita navegar por estruturas internas para abrir estabilidade por bin ou por variável |
| `report()` | Relatório auditável consolidado | Junta score, penalidades, cortes e racional em uma tabela única |
| `BinComparator` | Comparação champion challenger | Continua sendo a peça central quando o problema é escolher entre múltiplos candidatos |

## Fluxo recomendado para candidato único

```python
binner = Binner(
    strategy="supervised",
    score_strategy="generalization_v1",
    max_n_bins=5,
    check_stability=True,
)

binner.fit(df, y="target", column="score", time_col="month")
score_bins = binner.transform(df["score"])
summary = binner.summary()
score_details = binner.score_details()
diagnostics = binner.diagnostics(kind="bin")
report = binner.report()
```

Esse fluxo novo preserva o core introduzido em `v1.1.0`:

- `legacy`
- `generalization_v1`
- `score_weights`
- `normalization_strategy`
- `woe_shrinkage_strength`
- `objective_kwargs`

## Onde o Optuna entra

O Optuna continua sendo uma camada opcional de busca.

A melhoria recente foi de ergonomia da API pública, não de mudança conceitual do objective. Ou seja:

- o score pós-`v1.1.0` continua o mesmo
- o acesso ao score ficou mais simples
- o uso com e sem Optuna continua suportado

## Estratégias de score

Hoje a API expõe duas estratégias explícitas:

- `legacy`
  Mantém o score histórico orientado a maximização.
- `generalization_v1`
  Introduz um objective orientado a generalização temporal e minimização.

Exemplo:

```python
binner = Binner(
    strategy="supervised",
    check_stability=True,
    use_optuna=True,
    time_col="month",
    score_strategy="generalization_v1",
    score_weights={
        "temporal_variance_weight": 0.22,
        "window_drift_weight": 0.18,
        "rank_inversion_weight": 0.20,
        "separation_weight": 0.20,
        "entropy_weight": 0.08,
        "psi_weight": 0.12,
    },
    normalization_strategy="absolute",
    woe_shrinkage_strength=40.0,
    strategy_kwargs={"n_trials": 10},
)
```

## Próximos passos

- [Quickstart](../quickstart/)
- [Exemplos](../examples/)
- [Benchmark PD vintage](../../methodology/pd-vintage-benchmark/)
