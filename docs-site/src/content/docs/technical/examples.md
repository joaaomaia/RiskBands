---
title: "Exemplos"
description: "Scripts e notebooks para quickstart, benchmark, auditoria e demonstração da API amigável do RiskBands."
---

## Comece por aqui

### Notebook de ergonomia da API

É a porta de entrada recomendada para quem quer aprender o RiskBands com um fluxo mais familiar de pandas e sklearn.

- [Notebook sintético com Plotly](https://github.com/joaaomaia/RiskBands/blob/master/examples/riskbands_synthetic_plotly_comparative_demo.ipynb)

Esse material mostra:

- `fit(df, y="target", column="score", time_col="month")`
- `transform(df["score"])`
- `summary()`
- `binning_table()`
- `score_details()`
- `diagnostics()`
- comparação entre `legacy` e `stable`

### Quickstart de estabilidade temporal

É a porta de entrada mais curta para a camada temporal, agora já com tabela de score, auditoria e export auditável.

- [Script do quickstart](https://github.com/joaaomaia/RiskBands/blob/master/examples/temporal_stability/temporal_stability_example.py)
- [Notebook do quickstart](https://github.com/joaaomaia/RiskBands/blob/master/examples/temporal_stability/temporal_stability_example.ipynb)

Esse fluxo já mostra:

- `score_table()`
- `audit_table()`
- `export_binnings_json(...)`
- `export_bundle(...)`
- `plot_bad_rate_over_time(...)`
- `plot_bad_rate_heatmap(...)`
- `plot_bin_share_over_time(...)`
- `plot_score_components(...)`

### PD vintage champion challenger

É o exemplo de crédito mais direto para comparação entre candidatos.

- [Script champion challenger](https://github.com/joaaomaia/RiskBands/blob/master/examples/pd_vintage_champion_challenger/pd_vintage_champion_challenger.py)
- [Notebook champion challenger](https://github.com/joaaomaia/RiskBands/blob/master/examples/pd_vintage_champion_challenger/pd_vintage_champion_challenger.ipynb)

### Benchmark PD vintage

É a vitrine metodológica mais forte do projeto hoje.

- [Script do benchmark](https://github.com/joaaomaia/RiskBands/blob/master/examples/pd_vintage_benchmark/pd_vintage_benchmark.py)
- [Notebook do benchmark](https://github.com/joaaomaia/RiskBands/blob/master/examples/pd_vintage_benchmark/pd_vintage_benchmark.ipynb)

Use este material quando a pergunta principal for:

> por que um candidato com IV agregado mais forte ainda pode ser a escolha errada para crédito quando o tempo entra na decisão?

### Demo do score `stable`

É o exemplo mínimo para enxergar a mudança entre o score legado e a estratégia temporal recomendada no estado atual do projeto.

- [Script da demo](https://github.com/joaaomaia/RiskBands/blob/master/examples/stable_score/stable_score_demo.py)

## Ordem de leitura sugerida

### Se você quer começar pela API

1. Notebook sintético com Plotly
2. Quickstart
3. Auditoria e plots
4. Visão geral da API
5. PD vintage champion challenger
6. Benchmark PD vintage

### Se você quer começar pela tese metodológica

1. Por que RiskBands
2. Por que não usar apenas OptimalBinning
3. Benchmark PD vintage
4. Como ler os gráficos
