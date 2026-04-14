---
title: "Exemplos"
description: "Scripts e notebooks para quickstart, benchmark e demonstracao da API amigavel do RiskBands."
---

## Comece por aqui

### Notebook de ergonomia da API

E a porta de entrada recomendada para quem quer aprender o RiskBands com um
fluxo mais familiar de pandas e sklearn.

- [Notebook sintetico com Plotly](https://github.com/joaaomaia/RiskBands/blob/master/examples/riskbands_synthetic_plotly_comparative_demo.ipynb)

Esse material mostra:

- `fit(df, y="target", column="score", time_col="month")`
- `transform(df["score"])`
- `summary()`
- `binning_table()`
- `score_details()`
- `diagnostics()`
- comparacao entre `legacy` e `stable`

### Benchmark PD vintage

E a vitrine metodologica mais forte do projeto hoje.

- [Script do benchmark](https://github.com/joaaomaia/RiskBands/blob/master/examples/pd_vintage_benchmark/pd_vintage_benchmark.py)
- [Notebook do benchmark](https://github.com/joaaomaia/RiskBands/blob/master/examples/pd_vintage_benchmark/pd_vintage_benchmark.ipynb)

Use este material quando a pergunta principal for:

> por que um candidato com IV agregado mais forte ainda pode ser a escolha errada para credito quando o tempo entra na decisao?

### PD vintage champion challenger

E o exemplo de credito mais direto para comparacao entre candidatos.

- [Script champion challenger](https://github.com/joaaomaia/RiskBands/blob/master/examples/pd_vintage_champion_challenger/pd_vintage_champion_challenger.py)
- [Notebook champion challenger](https://github.com/joaaomaia/RiskBands/blob/master/examples/pd_vintage_champion_challenger/pd_vintage_champion_challenger.ipynb)

### Quickstart de estabilidade temporal

E a porta de entrada mais curta para o nucleo temporal da biblioteca.

- [Script do quickstart](https://github.com/joaaomaia/RiskBands/blob/master/examples/temporal_stability/temporal_stability_example.py)
- [Notebook do quickstart](https://github.com/joaaomaia/RiskBands/blob/master/examples/temporal_stability/temporal_stability_example.ipynb)

### Demo do score `stable`

E o exemplo minimo para enxergar a mudanca entre o score legado e a estrategia
temporal recomendada no estado atual do projeto.

- [Script da demo](https://github.com/joaaomaia/RiskBands/blob/master/examples/stable_score/stable_score_demo.py)

## Ordem de leitura sugerida

### Se voce quer comecar pela API

1. Notebook sintetico com Plotly
2. Quickstart
3. Visao geral da API
4. PD vintage champion challenger
5. Benchmark PD vintage

### Se voce quer comecar pela tese metodologica

1. Por que RiskBands
2. Por que nao usar apenas OptimalBinning
3. Benchmark PD vintage
4. Como ler os graficos
