---
title: "Optuna"
description: "Quando usar Optuna no RiskBands, como ele se conecta ao mesmo objective e qual o trade-off de custo."
---

## Com e sem Optuna

O RiskBands funciona bem nos dois modos:

- sem Optuna
- com Optuna

A lógica de score é a mesma. O que muda com Optuna é o uso de uma busca externa para encontrar configurações melhores de binning.

## Quando faz sentido não usar

Comece sem Optuna quando:

- você está explorando a API
- quer um fluxo curto e previsível
- já tem uma ideia razoável da configuração
- o custo computacional precisa ser baixo

Esse costuma ser o melhor ponto de partida para onboarding.

## Quando faz sentido usar

Considere Optuna quando:

- você está comparando várias configurações supervisionadas
- quer explorar trade-offs com menos tentativa manual
- o dataset e o problema justificam uma busca extra
- você quer usar o mesmo objective `stable` em uma busca mais ampla

## Como ele se encaixa no fluxo

```python
from riskbands import Binner

binner = Binner(
    strategy="supervised",
    use_optuna=True,
    score_strategy="stable",
    strategy_kwargs={"n_trials": 20},
    check_stability=True,
)

binner.fit(df, y="target", column="score", time_col="month")
```

## O que continua igual

Mesmo com Optuna:

- `score_strategy` continua valendo
- `normalization_strategy` continua valendo
- `woe_shrinkage_strength` continua valendo
- o objective continua o mesmo dentro e fora da busca

Isso evita uma separação artificial entre "score do fluxo normal" e "score do fluxo com otimização".

## Trade-off de custo

Vale pensar em três perguntas:

1. O ganho potencial justifica o custo extra?
2. O problema é sensível o suficiente para se beneficiar da busca?
3. Você está em uma etapa exploratória ou em uma etapa de consolidação?

Se a resposta ainda não estiver clara, comece sem Optuna e ligue depois.

## O que olhar no resultado

Depois do `fit`, continue usando a mesma camada de inspeção:

- `summary()`
- `score_details()`
- `report()`
- `diagnostics()`
- `best_params_` quando `use_optuna=True`
