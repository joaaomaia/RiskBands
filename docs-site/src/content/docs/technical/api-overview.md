---
title: "Visao geral da API"
description: "Mapa da superficie publica do RiskBands, com foco em onboarding, pandas-first e acesso simples ao score `stable`."
---

## Porta de entrada recomendada

Na maior parte dos casos, o fluxo ideal para um usuario novo eh:

1. instanciar `Binner`
2. rodar `fit(...)`
3. inspecionar `summary()`, `score_details()` e `report()`
4. aplicar `transform(...)` no mesmo formato de entrada que voce ja usa no pandas

O projeto agora favorece esse caminho sem esconder configuracoes avancadas do
score.

## Superficie publica principal

```python
from riskbands import Binner, BinComparator
from riskbands.temporal_stability import (
    ks_over_time,
    psi_over_time,
    temporal_separability_score,
)
```

## O que ficou mais amigavel

Sem mexer agressivamente no core, a API publica do `Binner` ficou mais proxima
de padroes familiares de sklearn e pandas:

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

Tambem foram adicionados aliases mais amigaveis para configuracao:

- `max_n_bins` como alias de `max_bins`
- `monotonic_trend` como alias de `monotonic`

## Blocos centrais

| Componente | Papel no fluxo | Por que importa |
| --- | --- | --- |
| `Binner` | Porta de entrada principal | Ajusta, transforma, resume e expoe score e diagnostico em uma superficie mais amigavel |
| `summary()` | Resumo curto pos-fit | Ajuda a entender rapidamente bins, IV e score |
| `score_details()` | Detalhamento do objective | Expoe score final, componentes, normalizacao e pesos |
| `diagnostics()` | Leitura temporal rapida | Evita navegar por estruturas internas para abrir estabilidade por bin ou por variavel |
| `report()` | Relatorio auditavel consolidado | Junta score, penalidades, cortes e racional em uma tabela unica |
| `BinComparator` | Comparacao champion challenger | Continua sendo a peca central quando o problema eh escolher entre multiplos candidatos |

## Fluxo recomendado para candidato unico

```python
binner = Binner(
    strategy="supervised",
    score_strategy="stable",
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

Esse fluxo preserva o core introduzido nas releases recentes:

- `legacy`
- `stable`
- `score_weights`
- `normalization_strategy`
- `woe_shrinkage_strength`
- `objective_kwargs`

## Onde o Optuna entra

O Optuna continua sendo uma camada opcional de busca.

A melhoria recente foi de ergonomia da API publica, nao de mudanca conceitual
do objective. Ou seja:

- o score continua o mesmo
- o acesso ao score ficou mais simples
- o uso com e sem Optuna continua suportado

## Estrategias de score

Hoje a API expoe duas estrategias explicitas:

- `legacy`
  Mantem o score historico orientado a maximizacao.
- `stable`
  Introduz o objective orientado a robustez temporal e minimizacao.

Exemplo:

```python
binner = Binner(
    strategy="supervised",
    check_stability=True,
    use_optuna=True,
    time_col="month",
    score_strategy="stable",
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

## O que olhar em seguida

Depois do primeiro `fit`, o trio mais util costuma ser:

- `summary()` para uma leitura curta
- `score_details()` para entender o score
- `diagnostics()` para abrir a estabilidade temporal

## Proximos passos

- [Quickstart](../quickstart/)
- [Score e estrategias](../score-strategy/)
- [Outputs e diagnostico](../outputs/)
- [Exemplos](../examples/)
- [Benchmark PD vintage](../methodology/pd-vintage-benchmark/)
