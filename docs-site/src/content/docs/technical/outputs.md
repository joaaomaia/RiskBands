---
title: "Outputs e diagnóstico"
description: "Como interpretar os principais outputs do Binner depois do fit, com foco em auditoria, score e leitura temporal."
---

## O que aparece depois do `fit`

Depois de ajustar um `Binner`, a API pública expõe artefatos mais amigáveis para inspeção:

- `binning_table()`
- `feature_binning_table()` e `get_binning_table()`
- `summary()`
- `score_details()`
- `score_table()`
- `report()`
- `audit_table()`
- `diagnostics()`
- `plot_stability()`
- `plot_bad_rate_over_time()`
- `plot_bad_rate_heatmap()`
- `plot_bin_share_over_time()`
- `plot_score_components()`
- `export_binnings_json()`
- `export_bundle()`

Também ficam disponíveis atributos pós-fit úteis, como:

- `binning_table_`
- `summary_`
- `score_details_`
- `score_table_`
- `audit_table_`
- `report_`
- `metadata_`
- `score_`
- `comparison_score_`

## `binning_table()`

Use quando quiser ver os cortes ou bins finais de forma direta.

Perguntas que ela ajuda a responder:

- quantos bins ficaram?
- quais intervalos ou grupos foram formados?
- qual é a ordem dos bins?

## `score_table()`

É a tabela mais curta para notebook quando a pergunta central é:

- por que esse score saiu assim?
- quais pesos entraram?
- quais componentes pesaram mais?
- qual normalização está ativa?

Ela expõe:

- `objective_score`
- `objective_preference_score`
- `weight_profile`
- `normalized_component_profile`
- `raw_component_profile`
- colunas detalhadas `objective_weight_*`, `objective_norm_*` e `objective_raw_*`

## `audit_table()`

É a tabela mais útil para revisão auditável e model risk.

Ela combina em uma única visão:

- cortes
- IV e score temporal
- score e penalidades
- cobertura, bins raros e reversões
- rationale resumido

## `diagnostics()`

Use `diagnostics(kind="bin")` quando quiser abrir o detalhe por bin e período.

Use `diagnostics(kind="variable")` quando quiser o resumo temporal agregado por variável.

É a melhor porta para investigar:

- cobertura
- volatilidade de event rate
- volatilidade de WoE
- share dos bins
- reversões de ranking
- quebras de monotonicidade

## `metadata_`

O metadata pós-fit agora é mais auditável.

Ele inclui:

- versão do `riskbands`
- `strategy`
- `score_strategy`
- `normalization_strategy`
- `woe_shrinkage_strength`
- pesos informados e pesos efetivos
- `target_name`
- `time_col`
- features ajustadas

## Export auditável

### `export_binnings_json(path)`

Gera um JSON único com:

- metadata geral do fit
- pesos do score
- bins por feature
- resumo, score details e auditoria por feature

### `export_bundle(path)`

Gera um pacote de auditoria com:

- JSON legível
- CSVs prontos para notebook ou governança
- tabelas por feature
- Parquet opcional quando houver engine disponível

## Leitura rápida do score

Uma regra simples:

- `legacy`: score bruto maior é melhor
- `stable`: score bruto menor é melhor

Se quiser uma régua consolidada para comparação entre estratégias, olhe também `objective_preference_score`.

## Exemplo

```python
binner.fit(df, y="target", column="score", time_col="month")

table = binner.binning_table()
score_table = binner.score_table()
audit_table = binner.audit_table()

binner.export_binnings_json("artifacts/riskbands_binnings.json")
binner.export_bundle("artifacts/run_2026_04_14")
```
