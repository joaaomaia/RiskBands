---
title: "Release Notes"
description: "Marcos de release em alto nivel para o pacote publico e para a documentacao oficial."
---

## Proximos passos

- benchmark com write-ups metodologicos mais ricos
- figuras exportadas para paginas da documentacao
- referencia de API mais profunda
- curadoria de publicacoes e notas tecnicas

## v2.0.0

Release de consolidacao publica:

- renomeacao definitiva do valor publico de `score_strategy` de `generalization_v1` para `stable`
- remocao do nome antigo da API publica, exemplos, smoke tests, labels e documentacao principal
- docs-site reorganizado para onboarding, primeiros passos e navegacao mais clara para novos usuarios
- paginas dedicadas para `score_strategy`, `normalization_strategy`, `woe_shrinkage_strength`, Optuna e interpretacao de outputs
- notebook e exemplos alinhados ao fluxo amigavel no estilo sklearn e pandas
- preparacao explicita do fluxo de release para validacao, GitHub Pages e publicacao em PyPI via Trusted Publishing

## v1.2.0

Evolucao importante da ergonomia da API publica:

- `Binner` mais alinhado a convencoes de sklearn e pandas
- suporte amigavel a `fit(df, y="target", column="feature")`
- `transform(...)` e `fit_transform(...)` com comportamento mais previsivel para `DataFrame` e `Series`
- aliases publicos como `max_n_bins` e `monotonic_trend`
- novos metodos de inspecao: `binning_table()`, `summary()`, `report()`, `score_details()`, `diagnostics()` e `plot_stability()`
- atributos pos-fit mais faceis de descobrir
- notebook novo com Plotly e dados sinteticos para onboarding da biblioteca

## v1.1.0

Evolucao importante da camada de scoring:

- caminho legado preservado explicitamente como `legacy`
- novo objective temporal introduzido e hoje exposto publicamente como `stable`
- pesos configuraveis, normalizacao `absolute` e shrink de WoE
- integracao consistente com `Binner`, `BinComparator`, relatorios auditaveis e Optuna
- novo exemplo minimo comparando `legacy` versus `stable`

## v1.0.0

Mudancas estruturais importantes ja refletidas no repositorio:

- rename destrutivo para `riskbands`
- `Binner` estabelecido como classe principal publica
- namespace legado `nasabinning` removido
- direcao de documentacao orientada a benchmark estabelecida nos exemplos do repositorio

## Fundacao da documentacao

Este site em Starlight e a primeira fundacao oficial da documentacao publica do RiskBands:

- porta tecnica
- porta metodologica
- deploy em GitHub Pages
- narrativa orientada a benchmark para usuarios de risco de credito
