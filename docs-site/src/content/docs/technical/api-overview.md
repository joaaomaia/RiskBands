---
title: "Visao geral da API"
description: "Mapa da superficie publica do RiskBands, com foco em onboarding, auditoria e leitura temporal amigavel."
---

## Porta de entrada recomendada

Na maior parte dos casos, o fluxo ideal para um usuario novo e:

1. instanciar `RiskBands`
2. rodar `fit(...)`
3. inspecionar `summary()`, `score_table()` e `audit_table()`
4. aplicar `transform(...)`
5. exportar os artefatos auditaveis
6. usar os plots publicos para leitura temporal

## Superficie publica principal

```python
from riskbands import RiskBands, Binner, BinComparator
from riskbands.temporal_stability import (
    ks_over_time,
    psi_over_time,
    temporal_separability_score,
)
```

`RiskBands` e o nome preferido. `Binner` segue disponivel para compatibilidade,
e `RiskBands is Binner` continua verdadeiro.

## Blocos centrais

| Componente | Papel no fluxo | Por que importa |
| --- | --- | --- |
| `RiskBands` / `Binner` | Porta de entrada principal | Ajusta, transforma, resume, exporta e plota sem exigir estruturas internas |
| `summary()` | Resumo curto pos-fit | Ajuda a entender bins, IV e score |
| `score_table()` | Explicacao curta do objective | Expoe score final, pesos e componentes mais relevantes |
| `audit_table()` | Revisao auditavel consolidada | Junta cuts, score, penalidades, cobertura e rationale |
| `diagnostics()` | Leitura temporal detalhada | Abre estabilidade por bin ou por variavel |
| `export_binnings_json()` | Artefato unico em JSON | Facilita versionamento e governanca |
| `export_bundle()` | Pacote completo de auditoria | Gera JSON, CSV e tabelas por feature |
| `BinComparator` | Comparacao champion/challenger | Ajuda a escolher entre multiplos candidatos |

## Fluxo recomendado para candidato unico

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
binner.export_bundle("artifacts/run_2026_04_14")
```

## Estrategias de score

A API expoe duas estrategias explicitas:

- `standard`: score historico orientado a maximizacao. `legacy` segue aceito
  apenas como alias compativel.
- `stable`: objective orientado a robustez temporal e minimizacao.

## Missing values

`missing_policy` aceita:

- `standard`: default compativel com o comportamento atual
- `separate_bin`: opt-in para bin explicito `Missing`
- `forbid`: erro em `fit` ou `transform` quando ha missing nas features selecionadas
- `merge`: opt-in pandas para rotear missing ao bin regular mais proximo aprendido no `fit`

`merge` exige `missing_merge_criterion="nearest_event_rate"` ou
`missing_merge_criterion="nearest_woe"`. O primeiro usa distancia absoluta de
taxa de evento; o segundo usa distancia absoluta de WoE. `missing_merge_fallback`
aceita `separate_bin` ou `raise` para missing que aparece no `transform` sem
decisao aprendida no `fit`.

Essas politicas nao fazem imputacao opaca. Em merge, `transform(...)` usa
somente a decisao aprendida no `fit` e nao aprende regra nova com a base de
aplicacao.

Depois do `fit`, inspecione `missing_profile_`, `missing_decision_log_`,
`missing_merge_candidates_` e `missing_merge_map_` para revisar volume, share,
event rate, criterio, candidatos, distancias e destino aprendido.

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

Depois do primeiro `fit`, o trio mais util costuma ser:

- `summary()` para uma leitura curta
- `score_table()` para entender o score e os pesos
- `audit_table()` para abrir a revisao auditavel

## Proximos passos

- [Quickstart](../quickstart/)
- [Auditoria e plots](../audit-and-plots/)
- [Outputs e diagnostico](../outputs/)
- [Missing policy](../missing-policy/)
- [Exemplos](../examples/)
