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
5. exportar os artefatos auditáveis
6. usar os plots públicos para leitura temporal

## Superfície pública principal

```python
from riskbands import RiskBands, Binner, BinComparator
from riskbands.temporal_stability import (
    ks_over_time,
    psi_over_time,
    temporal_separability_score,
)
```

## O que ficou mais amigável

Sem mexer agressivamente no core, a API pública do `Binner` ficou mais próxima de padrões familiares de sklearn e pandas:

- `fit(df, y="target", column="score")`
- `fit(df["score"], y=df["target"])`
- `transform(df)` ou `transform(df["score"])`
- `fit_transform(...)`
- `summary()`
- `score_details()`
- `score_table()`
- `report()`
- `audit_table()`
- `diagnostics()`
- `binning_table()`
- `feature_binning_table()`
- `plot_bad_rate_over_time()`
- `plot_bad_rate_heatmap()`
- `plot_bin_share_over_time()`
- `plot_score_components()`
- `export_binnings_json()`
- `export_bundle()`

Também foram adicionados aliases mais amigáveis para configuração:

- `max_n_bins` como alias de `max_bins`
- `monotonic_trend` como alias de `monotonic`

## Blocos centrais

| Componente | Papel no fluxo | Por que importa |
| --- | --- | --- |
| `RiskBands` / `Binner` | Porta de entrada principal | Ajusta, transforma, resume, exporta e plota sem exigir estruturas internas |
| `summary()` | Resumo curto pós-fit | Ajuda a entender rapidamente bins, IV e score |
| `score_table()` | Explicação curta do objective | Expõe score final, pesos e componentes mais relevantes |
| `audit_table()` | Revisão auditável consolidada | Junta cuts, score, penalidades, cobertura e rationale |
| `diagnostics()` | Leitura temporal detalhada | Abre estabilidade por bin ou por variável |
| `export_binnings_json()` | Artefato único em JSON | Facilita versionamento e governança |
| `export_bundle()` | Pacote completo de auditoria | Gera JSON, CSV e tabelas por feature |
| `BinComparator` | Comparação champion/challenger | Continua sendo a peça central quando o problema é escolher entre múltiplos candidatos |

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
binner.export_bundle("artifacts/run_2026_04_14")
```

## Estratégias de score

Hoje a API expõe duas estratégias explícitas:

- `standard`
  Mantém o score histórico orientado a maximização. `legacy` segue aceito apenas como alias compatível.
- `stable`
  Introduz o objective orientado a robustez temporal e minimização.

## Missing values

`missing_policy` aceita:

- `standard`: default compatível com o comportamento atual
- `separate_bin`: opt-in para bin explícito `Missing`
- `forbid`: erro em `fit` ou `transform` se houver missing nas features selecionadas

`separate_bin` nao faz imputacao opaca; ele torna o missing explicito e
auditavel. Merge policies ainda nao fazem parte do contrato publico.

Guia dedicado: [Missing policy](../missing-policy/).

Depois do `fit`, inspecione `missing_profile_` e `missing_decision_log_` para
ver volume, share, event rate e decisao tomada por variavel. Esses campos tambem
sao persistidos em `export_bundle(...)`.

Exemplo:

```python
binner = RiskBands(
    strategy="supervised",
    check_stability=True,
    time_col="month",
    missing_policy="separate_bin",
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
    woe_shrinkage_strength=40.0,
)
```

## O que olhar em seguida

Depois do primeiro `fit`, o trio mais útil costuma ser:

- `summary()` para uma leitura curta
- `score_table()` para entender o score e os pesos
- `audit_table()` para abrir a revisão auditável

## Próximos passos

- [Quickstart](../quickstart/)
- [Auditoria e plots](../audit-and-plots/)
- [Outputs e diagnóstico](../outputs/)
- [Missing policy](../missing-policy/)
- [Exemplos](../examples/)
