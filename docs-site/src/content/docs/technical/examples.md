---
title: "Exemplos"
description: "Scripts e notebooks para quickstart, benchmark e demonstração da API amigável do RiskBands."
---

## Comece por aqui

### Notebook de ergonomia da API

É a nova porta de entrada para quem quer aprender o RiskBands com um fluxo mais familiar de pandas/sklearn.

- [Notebook sintético com Plotly](https://github.com/joaaomaia/RiskBands/blob/master/examples/riskbands_synthetic_plotly_comparative_demo.ipynb)

Esse material mostra:

- `fit(df, y="target", column="score", time_col="month")`
- `transform(df["score"])`
- `summary()`
- `binning_table()`
- `score_details()`
- `diagnostics()`
- comparação entre `legacy` e `generalization_v1`

### Benchmark PD vintage

É a vitrine metodológica mais forte do projeto hoje.

- [Script do benchmark](https://github.com/joaaomaia/RiskBands/blob/master/examples/pd_vintage_benchmark/pd_vintage_benchmark.py)
- [Notebook do benchmark](https://github.com/joaaomaia/RiskBands/blob/master/examples/pd_vintage_benchmark/pd_vintage_benchmark.ipynb)

Use este material quando a pergunta principal for:

> por que um candidato com IV agregado mais forte ainda pode ser a escolha errada para crédito quando o tempo entra na decisão?

### PD vintage champion challenger

É o exemplo de crédito mais direto para comparação entre candidatos.

- [Script champion challenger](https://github.com/joaaomaia/RiskBands/blob/master/examples/pd_vintage_champion_challenger/pd_vintage_champion_challenger.py)
- [Notebook champion challenger](https://github.com/joaaomaia/RiskBands/blob/master/examples/pd_vintage_champion_challenger/pd_vintage_champion_challenger.ipynb)

### Quickstart de estabilidade temporal

É a porta de entrada mais curta para o núcleo temporal da biblioteca.

- [Script do quickstart](https://github.com/joaaomaia/RiskBands/blob/master/examples/temporal_stability/temporal_stability_example.py)
- [Notebook do quickstart](https://github.com/joaaomaia/RiskBands/blob/master/examples/temporal_stability/temporal_stability_example.ipynb)

### Demo do generalization objective

É o exemplo mínimo para enxergar a mudança entre o score legado e o objective temporal pós-`v1.1.0`.

- [Script da demo](https://github.com/joaaomaia/RiskBands/blob/master/examples/generalization_objective/generalization_objective_demo.py)

## Ordem de leitura sugerida

### Se você quer começar pela API

1. Notebook sintético com Plotly
2. Quickstart
3. Visão geral da API
4. PD vintage champion challenger
5. Benchmark PD vintage

### Se você quer começar pela tese metodológica

1. Por que RiskBands
2. Por que não usar apenas OptimalBinning
3. Benchmark PD vintage
4. Como ler os gráficos
