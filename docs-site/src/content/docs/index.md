---
title: "Documentação RiskBands"
description: "Documentação oficial do RiskBands para binning com robustez temporal, score estável, onboarding amigável e fluxos prontos para crédito."
template: splash
hero:
  title: RiskBands
  tagline: >-
    Binning para risco de crédito com foco em robustez temporal. O RiskBands
    ajuda a sair de uma leitura estática de IV para uma decisão mais defensável
    entre separação, estabilidade e auditabilidade.
  actions:
    - text: Primeiros passos
      link: ./technical/quickstart/
      icon: right-arrow
    - text: Entender o score stable
      link: ./technical/score-strategy/
      icon: right-arrow
      variant: minimal
features:
  - title: Começo rápido
    description: Instalação, primeiro exemplo mínimo e fluxo recomendado com `Binner` no estilo sklearn/pandas.
    link: ./technical/quickstart/
  - title: Score strategy
    description: Entenda `legacy` vs `stable`, quando usar cada um e como pensar separação versus robustez temporal.
    link: ./technical/score-strategy/
  - title: Outputs fáceis de ler
    description: Veja como interpretar `summary()`, `report()`, `score_details()`, `diagnostics()` e `binning_table()`.
    link: ./technical/outputs/
  - title: Optuna sem acoplamento
    description: Descubra quando vale ligar a busca externa e como ela se encaixa no mesmo objective do fluxo sem Optuna.
    link: ./technical/optuna/
  - title: Benchmark PD vintage
    description: A vitrine metodológica que mostra quando o binning estático deixa de contar a história inteira.
    link: ./methodology/pd-vintage-benchmark/
  - title: Evolução do projeto
    description: Veja o que mudou desde `v1.0.0`, incluindo score estável, ergonomia nova e maturidade de release.
    link: ./reference/after-v1-0/
---

## O que é o RiskBands

O RiskBands é uma biblioteca Python para construir, comparar e auditar candidatos
de binning quando a pergunta real não é apenas "qual corte tem IV maior?", mas:

> qual solução continua mais defensável quando o tempo entra na análise?

Ele foi pensado para casos como:

- modelos de PD
- scorecards de crédito
- leitura por safra ou vintage
- variáveis com drift temporal
- estruturas com bins raros, cobertura frágil ou reversões de ranking

## Por que usar

O `OptimalBinning` já resolve muito bem o corte estático. O papel do RiskBands é
ajudar a decidir se esse corte ainda é a melhor resposta quando você abre o
comportamento por período.

Na prática, o projeto adiciona:

- diagnóstico temporal por variável, bin e período
- score orientado a robustez temporal com a estratégia `stable`
- comparação entre candidatos via `BinComparator`
- relatórios auditáveis para explicar por que um candidato venceu

## Caminho recomendado para um usuário novo

1. Instale a biblioteca em Python.
2. Rode o [Quickstart](./technical/quickstart/).
3. Leia [Score e estratégias](./technical/score-strategy/) para entender `stable`.
4. Use [Outputs e diagnóstico](./technical/outputs/) para aprender a interpretar o resultado.
5. Vá para [Exemplos](./technical/examples/) ou para o [Benchmark PD vintage](./methodology/pd-vintage-benchmark/).

## Fluxo mínimo

```python
from riskbands import Binner

binner = Binner(
    strategy="supervised",
    score_strategy="stable",
    max_n_bins=5,
    check_stability=True,
)

binner.fit(df, y="target", column="score", time_col="month")
summary = binner.summary()
score_details = binner.score_details()
```

## O que torna o score `stable` diferente

O `stable` não escolhe o melhor candidato apenas por IV estático.

Ele combina:

- variância temporal do WoE shrinkado
- drift entre janelas
- inversões de ranking entre bins
- separação
- entropia
- PSI

Tudo isso em uma forma comparável e orientada a minimização.

## Próximos passos

- Quer começar a usar? Vá para [Quickstart](./technical/quickstart/).
- Quer entender a estratégia recomendada? Vá para [Score e estratégias](./technical/score-strategy/).
- Quer evidência metodológica? Vá para [Benchmark PD vintage](./methodology/pd-vintage-benchmark/).
