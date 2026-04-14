---
title: "Outputs e diagnóstico"
description: "Como interpretar os principais outputs do Binner depois do fit."
---

## O que aparece depois do `fit`

Depois de ajustar um `Binner`, a API pública expõe artefatos mais amigáveis para inspeção:

- `binning_table()`
- `summary()`
- `report()`
- `score_details()`
- `diagnostics()`
- `plot_stability()`

Também ficam disponíveis atributos pós-fit úteis, como:

- `binning_table_`
- `summary_`
- `report_`
- `score_details_`
- `score_`
- `comparison_score_`
- `feature_name_`
- `target_name_`

## `binning_table()`

Use quando quiser ver os cortes ou bins finais de forma direta.

Perguntas que ela ajuda a responder:

- quantos bins ficaram?
- quais intervalos ou grupos foram formados?
- como o binning final está organizado?

## `summary()`

É o resumo curto e amigável do resultado.

Normalmente é a primeira tabela para olhar no notebook.

Ela ajuda a responder:

- qual estratégia foi usada?
- qual foi o score final?
- qual foi o IV?
- existem alertas temporais relevantes?

## `score_details()`

É a tabela mais útil para entender o objective.

Ela expõe, por variável:

- `score_strategy`
- direção do objective
- `objective_score`
- `objective_preference_score`
- componentes raw
- componentes normalizados
- pesos efetivos
- `normalization_strategy`
- `woe_shrinkage_strength`

## `diagnostics()`

Use `diagnostics(kind="bin")` quando quiser abrir o detalhe por bin e período.

Use `diagnostics(kind="variable")` quando quiser o resumo temporal agregado por variável.

É a melhor porta para investigar:

- cobertura
- volatilidade de event rate
- volatilidade de WoE
- shares de bin
- reversões de ranking
- quebras de monotonicidade

## `report()`

É a tabela consolidada para auditoria e decisão.

Ela junta em um único lugar:

- cortes
- métricas estáticas
- métricas temporais
- objective score
- penalizações
- racional resumido

## `plot_stability()`

Use quando quiser uma leitura visual do comportamento temporal dos bins.

Ele é especialmente útil para:

- notebooks
- validação exploratória
- comunicação com times menos técnicos

## Leitura rápida do score

Uma regra simples:

- `legacy`: score bruto maior é melhor
- `stable`: score bruto menor é melhor

Se quiser uma régua consolidada para comparação entre estratégias, olhe também `objective_preference_score`.

## Exemplo

```python
binner.fit(df, y="target", column="score", time_col="month")

table = binner.binning_table()
summary = binner.summary()
details = binner.score_details()
diagnostics = binner.diagnostics(kind="bin")
report = binner.report()
```
