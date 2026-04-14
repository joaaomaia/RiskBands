---
title: "Score e estratégias"
description: "Como pensar `strategy`, `score_strategy`, `stable`, `normalization_strategy` e `woe_shrinkage_strength` no RiskBands."
---

## Dois níveis de estratégia

No RiskBands, vale separar duas decisões:

1. `strategy`
   Decide como o binning é construído.
2. `score_strategy`
   Decide como os candidatos são avaliados e comparados.

## `strategy`

Hoje a API expõe principalmente:

- `supervised`
- `unsupervised`

Em geral:

- use `supervised` quando o target já está disponível e você quer cortes guiados pela separação;
- use `unsupervised` quando quer uma estrutura mais simples ou um baseline interno de comparação.

## `score_strategy`

Os valores públicos válidos agora são:

- `legacy`
- `stable`

`stable` substitui a nomenclatura pública usada anteriormente e passa a ser o nome recomendado daqui para frente.

## Quando usar `stable`

`stable` é a estratégia preferida quando a pergunta real é:

> entre candidatos plausíveis, qual equilibra melhor separação e robustez temporal?

Ele é especialmente útil quando você se importa com:

- variância temporal do WoE
- drift entre janelas
- inversões de ranking entre bins
- PSI
- separação suficiente sem sacrificar estabilidade

Em termos práticos, `stable` é orientado a minimização:

- menor `objective_score` é melhor
- maior `objective_preference_score` continua ajudando em comparações consolidadas

## Quando usar `legacy`

`legacy` continua útil quando você quer:

- reproduzir a leitura histórica do projeto
- comparar com o comportamento anterior
- usar um score mais próximo da formulação antiga baseada em componentes positivos menos penalidades

## `normalization_strategy`

Hoje o valor suportado é:

- `absolute`

Ele existe para colocar os componentes do objective em escala comparável mesmo quando apenas um candidato está sendo avaliado.

Na prática:

- evita somar grandezas incompatíveis
- ajuda a leitura dos componentes normalizados em `score_details()`
- mantém o objective utilizável com e sem Optuna

## `woe_shrinkage_strength`

Esse parâmetro controla o quanto o WoE temporal é puxado para uma referência mais estável antes de entrar nos componentes do score.

Intuição prática:

- valor maior: mais suavização, menos sensibilidade a ruído e bins pequenos
- valor menor: mais fidelidade ao comportamento observado, com maior sensibilidade a oscilação

Quando aumentar:

- bases pequenas
- bins raros
- séries temporais curtas ou barulhentas

Quando reduzir:

- amostra maior
- bins bem suportados
- necessidade de capturar variações temporais mais finas

## Exemplo completo

```python
from riskbands import Binner

binner = Binner(
    strategy="supervised",
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
    woe_shrinkage_strength=35.0,
    check_stability=True,
)
```

## Como pensar separação versus estabilidade

Uma regra prática:

- se você só maximiza IV estático, pode escolher um candidato frágil no tempo;
- se você só maximiza estabilidade, pode escolher um candidato quase inútil;
- `stable` tenta equilibrar essas duas forças explicitamente.

## Próximos passos

- [Outputs e diagnóstico](../outputs/)
- [Optuna](../optuna/)
- [Visão geral da API](../api-overview/)
