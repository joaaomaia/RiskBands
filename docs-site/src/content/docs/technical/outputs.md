---
title: "Outputs e diagnostico"
description: "Como interpretar os principais outputs do Binner depois do fit, com foco em auditoria, score e leitura temporal."
---

## O que aparece depois do `fit`

Depois de ajustar um `Binner`, a API publica expoe artefatos amigaveis:

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

Tambem ficam disponiveis atributos pos-fit como:

- `binning_table_`
- `summary_`
- `score_details_`
- `score_table_`
- `audit_table_`
- `report_`
- `metadata_`
- `score_`
- `comparison_score_`

## Tabelas principais

`binning_table()` mostra cortes ou bins finais. `score_table()` e a tabela curta
para explicar objective, pesos, componentes normalizados e componentes raw.
`audit_table()` combina cortes, IV, score temporal, penalidades, cobertura,
bins raros, reversoes e rationale resumido.

## Diagnostico temporal

Use `diagnostics(kind="bin")` para abrir detalhe por bin e periodo. Use
`diagnostics(kind="variable")` para resumo temporal agregado por variavel.

Essa e a melhor porta para investigar:

- cobertura
- volatilidade de event rate
- volatilidade de WoE
- share dos bins
- reversoes de ranking
- quebras de monotonicidade

## Metadata

`metadata_` inclui versao do `riskbands`, estrategia, `score_strategy`,
`normalization_strategy`, `woe_shrinkage_strength`, pesos, `target_name`,
`time_col` e features ajustadas.

## Export auditavel

`export_binnings_json(path)` gera um JSON unico com metadata, pesos do score,
bins por feature, resumo, score details e auditoria por feature.

`export_bundle(path)` gera JSON legivel, CSVs, tabelas por feature e Parquet
opcional quando houver engine disponivel.

Bundles tambem persistem a trilha de missing values quando disponivel:
`missing_policy`, `effective_missing_policy`, `missing_profile`,
`missing_decision_log`, `missing_merge_criterion`, `missing_merge_fallback`,
`missing_merge_candidates` e `missing_merge_map`.

Esses campos registram a decisao de tratamento de missing values. Eles nao
representam imputacao opaca.

Use `missing_profile_` para revisar volume, share e event rate dos missing por
variavel. Use `missing_decision_log_` para ver se a acao foi preservar
`standard`, criar bin `Missing` com `separate_bin`, bloquear com `forbid` ou
rotear missing com `merge`. Para merge, use `missing_merge_candidates_` para
revisar candidatos e distancias e `missing_merge_map_` para ver o destino
aprendido.

Guia dedicado: [Missing policy](../missing-policy/).

## Leitura rapida do score

- `standard`: score bruto maior e melhor
- `stable`: score bruto menor e melhor

Para uma regua consolidada entre estrategias, veja `objective_preference_score`.

## Exemplo

```python
binner.fit(df, y="target", column="score", time_col="month")

table = binner.binning_table()
score_table = binner.score_table()
audit_table = binner.audit_table()

binner.export_binnings_json("artifacts/riskbands_binnings.json")
binner.export_bundle("artifacts/run_2026_04_14")
```
