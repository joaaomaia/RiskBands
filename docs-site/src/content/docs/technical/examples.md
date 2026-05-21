---
title: "Exemplos"
description: "Scripts e notebooks para quickstart, benchmark, auditoria e demonstração da API amigável do RiskBands."
---

## Comece por aqui

### Notebook de ergonomia da API

Porta de entrada recomendada para aprender o RiskBands com um fluxo familiar de
pandas e sklearn.

- [Notebook sintético com Plotly](https://github.com/joaaomaia/RiskBands/blob/main/examples/riskbands_synthetic_plotly_comparative_demo.ipynb)

Esse material mostra:

- `fit(df, y="target", column="score", time_col="month")`
- `transform(df["score"])`
- `summary()`
- `binning_table()`
- `score_details()`
- `diagnostics()`
- comparação entre `standard` e `stable`

### Quickstart de estabilidade temporal

- [Script do quickstart](https://github.com/joaaomaia/RiskBands/blob/main/examples/temporal_stability/temporal_stability_example.py)
- [Notebook do quickstart](https://github.com/joaaomaia/RiskBands/blob/main/examples/temporal_stability/temporal_stability_example.ipynb)

Esse fluxo mostra `score_table()`, `audit_table()`, export JSON/bundle e plots
públicos para leitura temporal.

### Missing policy pandas e PySpark

Use estes scripts quando a pergunta principal for como tratar missing values de
forma auditável sem imputação opaca.

- [Demo pandas de missing policy](https://github.com/joaaomaia/RiskBands/blob/main/examples/missing_policy/missing_policy_pandas_demo.py)
- [Demo PySpark de missing policy](https://github.com/joaaomaia/RiskBands/blob/main/examples/missing_policy/missing_policy_pyspark_demo.py)
- [Diagnóstico comparativo de missing policy](https://github.com/joaaomaia/RiskBands/blob/main/examples/missing_policy/missing_policy_comparison_demo.py)
- [Exemplo sintético de crédito com missing merge](https://github.com/joaaomaia/RiskBands/blob/main/examples/missing_policy/credit_risk_missing_merge_demo.py)

Eles mostram:

- `missing_policy="standard"`
- `missing_policy="separate_bin"`
- `missing_policy="forbid"`
- `missing_policy="merge"` com `nearest_event_rate`
- `missing_policy="merge"` com `nearest_woe`
- `missing_profile_`
- `missing_decision_log_`
- `missing_merge_candidates_`
- bundle com campos de missing policy e missing merge
- guarda opcional para PySpark
- Spark sampled-to-pandas para missing merge quando o extra Spark esta disponivel
- caveats de amostragem em validacao, bundle e audit report
- comparação entre `standard`, `separate_bin`, `forbid`, `merge + nearest_event_rate` e `merge + nearest_woe`
- exemplo sintético de risco de crédito sem dados reais

### Relatório de Auditoria do Binning

- [Demo do audit report](https://github.com/joaaomaia/RiskBands/blob/main/examples/audit_report/audit_bundle_report_demo.py)

Esse fluxo mostra:

- dataset sintético pequeno;
- `missing_policy="merge"`;
- `missing_merge_criterion="nearest_event_rate"`;
- `export_audit_report("audit_report.html")`;
- `export_bundle("bundle")` com `audit_report.html` incluído por padrão;
- caminhos dos arquivos gerados sem abrir navegador automaticamente.

### PD vintage champion challenger

- [Script champion challenger](https://github.com/joaaomaia/RiskBands/blob/main/examples/pd_vintage_champion_challenger/pd_vintage_champion_challenger.py)
- [Notebook champion challenger](https://github.com/joaaomaia/RiskBands/blob/main/examples/pd_vintage_champion_challenger/pd_vintage_champion_challenger.ipynb)

### Benchmark PD vintage

- [Script do benchmark](https://github.com/joaaomaia/RiskBands/blob/main/examples/pd_vintage_benchmark/pd_vintage_benchmark.py)
- [Notebook do benchmark](https://github.com/joaaomaia/RiskBands/blob/main/examples/pd_vintage_benchmark/pd_vintage_benchmark.ipynb)

Use este material quando a pergunta principal for por que um candidato com IV
agregado mais forte ainda pode ser a escolha errada para crédito quando o tempo
entra na decisão.

### Demo do score `stable`

- [Script da demo](https://github.com/joaaomaia/RiskBands/blob/main/examples/stable_score/stable_score_demo.py)

## Ordem de leitura sugerida

### Se você quer começar pela API

1. Notebook sintético com Plotly
2. Quickstart
3. Auditoria e plots
4. Visão geral da API
5. Missing policy
6. Relatório de Auditoria do Binning
7. PD vintage champion challenger
8. Benchmark PD vintage

### Se você quer começar pela tese metodológica

1. Por que RiskBands
2. Por que não usar apenas OptimalBinning
3. Benchmark PD vintage
4. Como ler os graficos
