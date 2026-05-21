---
title: "Visão geral da API"
description: "Mapa da superfície pública do RiskBands, com foco em onboarding, auditoria e leitura temporal amigável."
---

## Porta de entrada recomendada

Na maior parte dos casos, o fluxo ideal para um usuário novo é:

1. instanciar `RiskBands`
2. rodar `fit(...)`
3. inspecionar `summary()`, `score_table()` e `audit_table()`
4. aplicar `transform(...)`
5. exportar os artefatos auditaveis
6. usar os plots publicos para leitura temporal

## Superfície pública principal

```python
from riskbands import RiskBands, Binner, BinComparator
from riskbands.temporal_stability import (
    ks_over_time,
    psi_over_time,
    temporal_separability_score,
)
```

`RiskBands` é o nome preferido. `Binner` segue disponível para compatibilidade,
e `RiskBands is Binner` continua verdadeiro.

## Blocos centrais

| Componente | Papel no fluxo | Por que importa |
| --- | --- | --- |
| `RiskBands` / `Binner` | Porta de entrada principal | Ajusta, transforma, resume, exporta e plota sem exigir estruturas internas |
| `summary()` | Resumo curto pos-fit | Ajuda a entender bins, IV e score |
| `score_table()` | Explicação curta do objective | Expõe score final, pesos e componentes mais relevantes |
| `audit_table()` | Revisão auditável consolidada | Junta cuts, score, penalidades, cobertura e rationale |
| `diagnostics()` | Leitura temporal detalhada | Abre estabilidade por bin ou por variável |
| `export_binnings_json()` | Artefato único em JSON | Facilita versionamento e governança |
| `export_audit_report()` | Relatório de Auditoria do Binning | Explica bundle, missing policies, merge, validação e limitações em linguagem auditável |
| `export_bundle()` | Pacote completo de auditoria | Gera JSON, CSV e tabelas por feature |
| `BinComparator` | Comparacao champion/challenger | Ajuda a escolher entre multiplos candidatos |

## Fluxo recomendado para candidato único

```python
binner = RiskBands(
    strategy="supervised",
    score_strategy="stable",
    max_n_bins=5,
    check_stability=True,
    missing_policy="standard",
)

binner.fit(df, y="target", column="score", time_col="month")

score_bins = binner.transform(df["score"])
summary = binner.summary()
score_table = binner.score_table()
audit_table = binner.audit_table()

binner.export_binnings_json("artifacts/riskbands_binnings.json")
binner.export_audit_report("artifacts/audit_report.html")
binner.export_bundle("artifacts/run_2026_04_14")
```

## Estratégias de score

A API expõe duas estratégias explícitas:

- `standard`: score histórico orientado a maximização. `legacy` segue aceito
  apenas como alias compatível.
- `stable`: objective orientado a robustez temporal e minimização.

## Missing values

`missing_policy` aceita:

- `standard`: default compatível com o comportamento atual
- `separate_bin`: opt-in para bin explícito `Missing`
- `forbid`: erro em `fit` ou `transform` quando ha missing nas features selecionadas
- `merge`: opt-in para rotear missing ao bin regular mais próximo aprendido no `fit`

`merge` exige `missing_merge_criterion="nearest_event_rate"` ou
`missing_merge_criterion="nearest_woe"`. O primeiro usa distância absoluta de
taxa de evento; o segundo usa distância absoluta de WoE. `missing_merge_fallback`
aceita `separate_bin` ou `raise` para missing que aparece no `transform` sem
decisão aprendida no `fit`.

Essas políticas não fazem imputação opaca. Em merge, `transform(...)` usa
somente a decisão aprendida no `fit` e não aprende regra nova com a base de
aplicação.

Em Spark, `merge` usa o caminho controlado sampled-to-pandas para `fit` e
aplica a decisão aprendida no `transform` com expressões Spark nativas e
`return_woe=False`. Revise metadados de amostragem, `source_profile_` e
`missing_sampling_diagnostics_` quando `fit(validate=True)` for usado.

Depois do `fit`, inspecione `missing_profile_`, `missing_decision_log_`,
`missing_merge_candidates_` e `missing_merge_map_` para revisar volume, share,
event rate, critério, candidatos, distâncias e destino aprendido.

Exemplo:

```python
binner = RiskBands(
    strategy="supervised",
    check_stability=True,
    time_col="month",
    missing_policy="merge",
    missing_merge_criterion="nearest_woe",
    missing_merge_fallback="separate_bin",
    score_strategy="stable",
)
```

Guia dedicado: [Missing policy](../missing-policy/).

## O que olhar em seguida

Depois do primeiro `fit`, o trio mais útil costuma ser:

- `summary()` para uma leitura curta
- `score_table()` para entender o score e os pesos
- `audit_table()` para abrir a revisão auditável

Para compartilhar o resultado com auditoria, governança ou model risk, use
`export_audit_report("audit_report.html")`. O HTML é standalone, print-friendly
e também entra no bundle por padrão via `export_bundle(...)`.

## Próximos passos

- [Quickstart](../quickstart/)
- [Auditoria e plots](../audit-and-plots/)
- [Outputs e diagnostico](../outputs/)
- [Missing policy](../missing-policy/)
- [Exemplos](../examples/)
