---
title: "Auditoria e plots"
description: "Como usar os exports auditáveis, as tabelas amigáveis e a nova camada pública de visualização do RiskBands."
---

## O que entrou nesta camada

O `Binner` agora expõe uma superfície pública mais direta para:

- auditoria de bins por feature
- export em JSON legível
- export de um bundle completo de governança
- score table e audit table prontas para notebook
- plots temporais e score components sem pivot manual

## Fluxo recomendado

```python
from pathlib import Path

from riskbands import Binner

binner = Binner(
    strategy="supervised",
    check_stability=True,
    score_strategy="stable",
    score_weights={
        "temporal_variance_weight": 0.24,
        "window_drift_weight": 0.16,
        "rank_inversion_weight": 0.18,
        "separation_weight": 0.20,
        "entropy_weight": 0.08,
        "psi_weight": 0.14,
    },
    normalization_strategy="absolute",
    woe_shrinkage_strength=35.0,
)

binner.fit(df, y="target", column="score", time_col="month")

score_table = binner.score_table()
audit_table = binner.audit_table()

binner.export_binnings_json("artifacts/riskbands_binnings.json")
binner.export_bundle("artifacts/run_2026_04_14")

binner.plot_bad_rate_over_time(df, y="target", column="score", time_col="month")
binner.plot_bad_rate_heatmap(df, y="target", column="score", time_col="month")
binner.plot_bin_share_over_time(df, y="target", column="score", time_col="month")
binner.plot_score_components(column="score")
```

## Export auditável

### `export_binnings_json(...)`

Use quando quiser um artefato único, legível e fácil de versionar.

O JSON inclui:

- metadata geral do fit
- versão do `riskbands`
- `strategy`, `score_strategy`, `normalization_strategy`
- `woe_shrinkage_strength`
- pesos usados no score
- lista de features
- bins por feature
- resumo, score details e auditoria por feature quando disponíveis

### `export_bundle(...)`

Use quando quiser um pacote pronto para governança, validação interna ou versionamento.

O bundle gera artefatos como:

- `metadata.json`
- `binnings.json`
- `summary.csv`
- `score_details.csv`
- `score_table.csv`
- `audit_table.csv`
- `report.csv`
- `diagnostics.csv` quando houver camada temporal
- `feature_tables/<feature>.csv`

Quando um engine de Parquet estiver disponível, o bundle também escreve `report.parquet` e `diagnostics.parquet`.

## Onde os pesos aparecem

Os pesos do score agora ficam explícitos em:

- `binner.metadata_`
- `score_table()`
- `audit_table()`
- `metadata.json`
- `binnings.json`

Isso facilita revisão técnica, model risk e replay da decisão de score.

## Tabelas mais diretas

### `score_table()`

É a visão mais curta para explicar o score.

Ela expõe:

- score final
- score de preferência comparável
- direção do objetivo
- normalização
- shrink de WoE
- perfis resumidos de pesos, componentes e penalidades
- colunas detalhadas de `objective_weight_*`, `objective_norm_*` e `objective_raw_*`

### `audit_table()`

É a tabela única para revisão auditável.

Ela combina:

- cortes finais
- IV e score temporal
- score e penalidades
- cobertura, bins raros e reversões
- rationale resumido

### `feature_binning_table(...)`

É um alias mais descobrível para `binning_table(...)`.

Também existe `get_binning_table(...)` para quem procura um nome mais explícito.

## Plots públicos

### `plot_bad_rate_over_time(...)`

Mostra a curva de event rate por bin ao longo do tempo, já com ordenação de bins e rótulos amigáveis.

### `plot_bad_rate_heatmap(...)`

Monta automaticamente o heatmap bin x safra, sem pivot manual.

### `plot_bin_share_over_time(...)`

Ajuda a detectar bins raros, sumindo em certas safras ou com share instável.

### `plot_score_components(...)`

Mostra, no mesmo painel, as contribuições ponderadas do objective e os pesos efetivos usados no score.

### `plot_event_rate_by_bin(...)` e `plot_woe(...)`

Servem como leitura rápida do comportamento estático do binning e do perfil médio de WoE.

## Próximos passos

- [Quickstart](../quickstart/)
- [Outputs e diagnóstico](../outputs/)
- [Exemplos](../examples/)
