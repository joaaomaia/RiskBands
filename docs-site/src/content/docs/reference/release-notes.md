---
title: "Release Notes"
description: "Marcos de release em alto nível para o pacote público e para a documentação oficial."
---

## Próximos passos

- benchmark com write-ups metodológicos mais ricos
- figuras exportadas para páginas da documentação
- referência de API mais profunda
- curadoria de publicações e notas técnicas

## v1.2.0

Evolução importante da ergonomia da API pública:

- `Binner` mais alinhado a convenções de sklearn e pandas
- suporte amigável a `fit(df, y="target", column="feature")`
- `transform(...)` e `fit_transform(...)` com comportamento mais previsível para `DataFrame` e `Series`
- aliases públicos como `max_n_bins` e `monotonic_trend`
- novos métodos de inspeção: `binning_table()`, `summary()`, `report()`, `score_details()`, `diagnostics()` e `plot_stability()`
- atributos pós-fit mais fáceis de descobrir
- notebook novo com Plotly e dados sintéticos para onboarding da biblioteca

## v1.1.0

Evolução importante da camada de scoring:

- caminho legado preservado explicitamente como `legacy`
- novo objective `generalization_v1` para generalização temporal
- pesos configuráveis, normalização `absolute` e shrink de WoE
- integração consistente com `Binner`, `BinComparator`, relatórios auditáveis e Optuna
- novo exemplo mínimo comparando `legacy` versus `generalization_v1`

## v1.0.0

Mudanças estruturais importantes já refletidas no repositório:

- rename destrutivo para `riskbands`
- `Binner` estabelecido como classe principal pública
- namespace legado `nasabinning` removido
- direção de documentação orientada a benchmark estabelecida nos exemplos do repositório

## Fundação da documentação

Este site em Starlight é a primeira fundação oficial da documentação pública do RiskBands:

- porta técnica
- porta metodológica
- deploy em GitHub Pages
- narrativa orientada a benchmark para usuários de risco de crédito
