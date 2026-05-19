---
title: "Outputs e diagnóstico"
description: "Como interpretar os principais outputs do Binner depois do fit, com foco em auditoria, score e leitura temporal."
---

## O que aparece depois do `fit`

Depois de ajustar um `Binner`, a API pública expõe artefatos amigáveis:

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
- `export_audit_report()`
- `export_bundle()`

Também ficam disponíveis atributos pós-fit como:

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

`binning_table()` mostra cortes ou bins finais. `score_table()` é a tabela curta
para explicar objective, pesos, componentes normalizados e componentes raw.
`audit_table()` combina cortes, IV, score temporal, penalidades, cobertura,
bins raros, reversões e rationale resumido.

## Diagnóstico temporal

Use `diagnostics(kind="bin")` para abrir detalhe por bin e período. Use
`diagnostics(kind="variable")` para resumo temporal agregado por variável.

Essa é a melhor porta para investigar:

- cobertura
- volatilidade de event rate
- volatilidade de WoE
- share dos bins
- reversoes de ranking
- quebras de monotonicidade

## Metadata

`metadata_` inclui versão do `riskbands`, estratégia, `score_strategy`,
`normalization_strategy`, `woe_shrinkage_strength`, pesos, `target_name`,
`time_col` e features ajustadas.

## Export auditável

`export_binnings_json(path)` gera um JSON único com metadata, pesos do score,
bins por feature, resumo, score details e auditoria por feature.

`export_audit_report(path)` gera `audit_report.html`: um relatório narrativo
HTML standalone, com CSS embutido, sem assets externos, print-friendly e
orientado a auditoria/model risk.

`export_bundle(path)` gera JSON legível, CSVs, tabelas por feature, Parquet
opcional quando houver engine disponível e `audit_report.html` por padrão.
Use `export_bundle(path, include_audit_report=False)` apenas quando precisar
manter o bundle sem o HTML narrativo.

Bundles também persistem a trilha de missing values quando disponível:
`missing_policy`, `effective_missing_policy`, `missing_profile`,
`missing_decision_log`, `missing_merge_criterion`, `missing_merge_fallback`,
`missing_merge_candidates` e `missing_merge_map`.

Esses campos registram a decisão de tratamento de missing values. Eles não
representam imputação opaca.

Use `missing_profile_` para revisar volume, share e event rate dos missing por
variável. Use `missing_decision_log_` para ver se a ação foi preservar
`standard`, criar bin `Missing` com `separate_bin`, bloquear com `forbid` ou
rotear missing com `merge`. Para merge, use `missing_merge_candidates_` para
revisar candidatos e distâncias e `missing_merge_map_` para ver o destino
aprendido.

Guia dedicado: [Missing policy](../missing-policy/).

## Relatório de Auditoria do Binning

O `audit_report.html` explica configuração, variáveis, políticas de missing,
decisões de merge, candidatos avaliados, validação, alertas, inventário do
bundle e limitações. Para merge, o texto deixa claro que a decisão foi aprendida
no `fit` e reutilizada no `transform`, sem recalcular event rate/WoE na base de
aplicacao.

O HTML é autocontido e pode ser impresso ou exportado para PDF pelo navegador.
Ele organiza evidências técnicas, mas não substitui validação formal
independente nem constitui certificação regulatória.

## Leitura rápida do score

- `standard`: score bruto maior e melhor
- `stable`: score bruto menor e melhor

Para uma régua consolidada entre estratégias, veja `objective_preference_score`.

## Exemplo

```python
binner.fit(df, y="target", column="score", time_col="month")

table = binner.binning_table()
score_table = binner.score_table()
audit_table = binner.audit_table()

binner.export_binnings_json("artifacts/riskbands_binnings.json")
binner.export_audit_report("artifacts/audit_report.html")
binner.export_bundle("artifacts/run_2026_04_14")
```
