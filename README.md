# RiskBands

Binning para risco de credito com foco em robustez temporal, comparacao entre
candidatos e racional auditavel.

[Documentacao oficial](https://joaaomaia.github.io/RiskBands/) |
[PyPI](https://pypi.org/project/riskbands/) |
[Benchmark PD vintage](https://joaaomaia.github.io/RiskBands/methodology/pd-vintage-benchmark/) |
[Quickstart](https://joaaomaia.github.io/RiskBands/technical/quickstart/) |
[Auditoria e plots](https://joaaomaia.github.io/RiskBands/technical/audit-and-plots/) |
[API](https://joaaomaia.github.io/RiskBands/technical/api-overview/) |
[Missing policy](https://joaaomaia.github.io/RiskBands/technical/missing-policy/)

---

## O que e o RiskBands

O RiskBands e uma biblioteca para construir, comparar e auditar candidatos de
binning quando o problema real nao e apenas maximizar uma metrica estatica, mas
tambem defender o resultado ao longo do tempo.

Ele foi pensado especialmente para contextos como:

- modelos de PD
- scorecards de credito
- variaveis com drift temporal
- leitura relevante por safra ou vintage
- estruturas com bins raros, baixa cobertura ou reversoes de ranking

A pergunta central do projeto e simples:

> Um binning que parece otimo no agregado continua defensavel quando voce abre o comportamento por safra?

## Onde o projeto se diferencia

O `OptimalBinning` ja resolve muito bem o problema de corte estatico. O
RiskBands nao tenta negar isso.

No fluxo supervisionado numerico do repositorio atual, o projeto reaproveita
`optbinning.OptimalBinning` no backend do corte estatico. O diferencial esta no
que vem depois:

- diagnostico temporal por variavel, bin e periodo
- penalizacoes estruturais para fragilidade, baixa cobertura e volatilidade
- comparacao entre candidatos via `BinComparator`
- score objetivo mais alinhado a trade-offs de risco de credito
- resumos auditaveis para explicar por que um candidato venceu

Em outras palavras:

- `OptimalBinning` puro ajuda a encontrar um bom corte estatico
- `RiskBands` ajuda a decidir se esse corte continua sendo a melhor resposta
  para credito quando o tempo entra na analise

## Arquitetura de score

O repositório agora expõe dois caminhos explícitos de score:

- `standard`
  Mantém o objetivo histórico baseado em componentes positivos menos penalidades.
  `legacy` segue aceito apenas como alias compatível.
- `stable`
  Introduz a estratégia pública recomendada para robustez temporal, orientada a
  minimização, com componentes normalizados e foco em equilíbrio entre
  separação e estabilidade.

O `stable` combina:

- variância temporal ponderada do WoE shrinkado
- drift entre janelas adjacentes
- penalidade de inversão de ranking entre bins
- penalidade de separação insuficiente
- entropy penalty para distribuições degeneradas
- PSI como proxy de estabilidade em produção

Todos os componentes são normalizados em modo absoluto, então o score funciona
mesmo quando apenas um candidato está sendo avaliado.

Os pesos padrão são:

- `temporal_variance_weight=0.22`
- `window_drift_weight=0.18`
- `rank_inversion_weight=0.20`
- `separation_weight=0.20`
- `entropy_weight=0.08`
- `psi_weight=0.12`

O shrink de WoE é tratado como camada de robustez, não como score isolado:

- WoE raw por bin e período
- shrink em direção ao WoE global do bin
- uso do WoE shrinkado nos componentes temporais

## Instalacao

Instalacao base:

```bash
pip install riskbands
```

Extra opcional para graficos Plotly e export HTML dos benchmarks:

```bash
pip install "riskbands[viz]"
```

Extra opcional para uso e testes com PySpark:

```bash
pip install "riskbands[spark]"
```

Para desenvolvimento, testes e notebooks:

```bash
git clone https://github.com/joaaomaia/RiskBands.git
cd RiskBands
pip install -e .[dev]
```

Pacote no PyPI: [riskbands](https://pypi.org/project/riskbands/).

## Como comecar

Porta tecnica:

- [Instalacao](https://joaaomaia.github.io/RiskBands/technical/installation/)
- [Quickstart](https://joaaomaia.github.io/RiskBands/technical/quickstart/)
- [Missing policy](https://joaaomaia.github.io/RiskBands/technical/missing-policy/)
- [Visao geral da API](https://joaaomaia.github.io/RiskBands/technical/api-overview/)
- [Exemplos](https://joaaomaia.github.io/RiskBands/technical/examples/)

Porta metodologica:

- [Por que RiskBands](https://joaaomaia.github.io/RiskBands/methodology/why-riskbands/)
- [Por que nao usar apenas OptimalBinning](https://joaaomaia.github.io/RiskBands/methodology/why-not-only-optimal-binning/)
- [Benchmark PD vintage](https://joaaomaia.github.io/RiskBands/methodology/pd-vintage-benchmark/)
- [Como ler os graficos](https://joaaomaia.github.io/RiskBands/methodology/how-to-read-the-charts/)
- [Robustez temporal em risco de credito](https://joaaomaia.github.io/RiskBands/methodology/temporal-robustness-in-credit-risk/)

## Tipos de entrada suportados

A API reconhece `pandas.DataFrame`, `pandas.Series` e, com o extra opcional
`riskbands[spark]`, `PySpark DataFrame`.

O fluxo pandas continua igual: `fit(df, y="target", column="score",
time_col="month")` ou uma lista de colunas em um `DataFrame` pandas.

No PySpark, o `fit` usa amostragem controlada por `sample_size`, converte a
amostra para pandas e reaproveita o motor estatistico atual. O `transform`
preserva `PySpark DataFrame` e usa expressoes Spark nativas.

## Variaveis categoricas e overrides

Colunas categoricas podem ser marcadas explicitamente com `force_categorical`.
O tratamento de categorias raras, valores missing e categorias desconhecidas no
`transform` e deterministico, com mapeamento aprendido no `fit`.

```python
binner = RiskBands(
    strategy="supervised",
    force_categorical=["rating_interno"],
)
```

Quando a inferencia automatica de tipo nao for suficiente, use
`force_numeric` e `force_categorical` para fixar a intencao. A mesma coluna nao
deve aparecer nas duas listas; isso e tratado como conflito.

```python
binner = RiskBands(
    strategy="supervised",
    force_numeric=["qtd_restritivos"],
    force_categorical=["rating_interno"],
)
```

## Missing values auditaveis

`missing_policy` controla como valores ausentes nas features selecionadas entram
no binning:

- `standard` e o default e preserva o comportamento historico congelado na
  Sprint A.
- `separate_bin` e opt-in e cria bin explicito `Missing`, incluindo missing
  categorico.
- `forbid` falha em `fit` ou `transform` quando houver missing nas features
  selecionadas.
- `merge` e opt-in para unir o grupo missing a um bin regular aprendido no
  `fit`, preservando a trilha auditavel.

Com `missing_policy="merge"`, escolha explicitamente o criterio:

- `missing_merge_criterion="nearest_event_rate"` escolhe o bin regular com
  menor distancia absoluta de event rate em relacao ao grupo missing no fit.
- `missing_merge_criterion="nearest_woe"` escolhe o bin regular com menor
  distancia absoluta de WoE em relacao ao grupo missing no fit.

`missing_merge_fallback="separate_bin"` mantem missing novo de transform como
`Missing` quando nao houve decisao aprendida no fit. `missing_merge_fallback="raise"`
falha nesse caso.

Bundles novos persistem `missing_policy`, `effective_missing_policy`,
`missing_profile`, `missing_decision_log`, `missing_merge_criterion`,
`missing_merge_fallback`, `missing_merge_candidates` e `missing_merge_map`
quando esses campos existem. Bundles antigos sem esses campos carregam como
`standard`, com campos de merge ausentes como `None`.

Guia dedicado:
[docs/missing_policy_user_guide.md](docs/missing_policy_user_guide.md) ou
[Missing policy no docs-site](https://joaaomaia.github.io/RiskBands/technical/missing-policy/).

Exemplo minimo:

```python
from riskbands import RiskBands

binner = RiskBands(
    max_bins=4,
    force_categorical=["rating"],
    missing_policy="separate_bin",
)

binner.fit(df, y="target", columns=["score", "rating"], validate=True)
df_binned = binner.transform(df[["score", "rating"]], validate=True)

print(binner.missing_profile_)
print(binner.missing_decision_log_)
```

Exemplo de merge auditavel:

```python
binner = RiskBands(
    max_bins=4,
    missing_policy="merge",
    missing_merge_criterion="nearest_event_rate",
    missing_merge_fallback="separate_bin",
)

binner.fit(df, y="target", column="score")
df_binned = binner.transform(df[["score"]])

print(binner.missing_profile_)
print(binner.missing_decision_log_)
print(binner.missing_merge_candidates_)
```

Troque o criterio para `missing_merge_criterion="nearest_woe"` quando a
similaridade por WoE for mais alinhada a revisao do scorecard. Em ambos os
casos, a decisao e aprendida somente no `fit`; `transform(...)` nao recalcula
destino usando a base de aplicacao.

Exemplos executaveis:

- `python examples/missing_policy/missing_policy_pandas_demo.py`
- `python examples/missing_policy/missing_policy_pyspark_demo.py`

## Destaques da versao 2.4.0

A versao 2.4.0 prepara a release de Spark missing merge, audit bundle narrativo,
docs publicas e exemplos:

- `missing_policy="standard"` permanece como default compativel.
- `missing_policy="merge"` continua auditavel em pandas com
  `nearest_event_rate` e `nearest_woe`.
- Spark transform aplica decisoes de missing merge aprendidas usando expressoes
  Spark nativas e `return_woe=False`.
- Spark fit com missing merge usa caminho controlado sampled-to-pandas, registra
  a caveat de amostragem e nao afirma aprendizado Spark-native no dataset
  completo.
- `fit(validate=True)` em Spark pode gerar `source_profile_`,
  diagnosticos sample-vs-source e `missing_sampling_diagnostics`.
- `audit_report.html` gera um relatorio narrativo standalone e print-friendly
  com configuracao, missing policies, merge, validacao, inventario do bundle e
  limitacoes.
- `export_bundle(...)` inclui `audit_report.html` por padrao, alem de metadata,
  CSVs, tabelas por feature e trilhas de missing merge quando disponiveis.
- A galeria Reveal.js do docs-site inclui uma apresentacao RiskBands Overview.
- `standard` e o nome canonico do score historico; `legacy` segue como alias
  compativel.
- pandas e PySpark seguem suportados, com PySpark opcional via
  `riskbands[spark]` e restrito a `pyspark>=3.5.2,<4`.

Fora do escopo desta versao: Spark-native full fit para missing merge, Spark
`return_woe=True`, `temporal_stable`, `monotonic_neighbor`, criterios adicionais
de merge, imputacao inteligente opaca, PDF nativo do audit report e garantia de
conformidade regulatoria.

## Export auditavel e supply chain

`export_bundle(...)` gera artefatos tabulares e JSON para auditoria. Nomes de
features usados nos artefatos exportados sao sanitizados para evitar paths
inseguros, mantendo a rastreabilidade dos nomes originais no manifest.

Dependencias de solver e verificacoes de supply chain ficam resumidas em
[docs/supply_chain_dependencies.md](docs/supply_chain_dependencies.md).

## Quickstart minimo

```python
import numpy as np
import pandas as pd

from riskbands import RiskBands

rng = np.random.default_rng(0)
n = 800

df = pd.DataFrame({"score": rng.normal(size=n)})
df["month"] = rng.choice([202301, 202302, 202303, 202304], size=n)

proba = 0.20 + 0.15 * df["score"] + 0.02 * (df["month"] - 202301)
proba = np.clip(proba, 0.01, 0.99)
df["target"] = (rng.random(n) < proba).astype(int)

binner = RiskBands(
    strategy="supervised",
    max_n_bins=5,
    check_stability=True,
    monotonic="ascending",
    min_event_rate_diff=0.03,
    score_strategy="stable",
    normalization_strategy="absolute",
    woe_shrinkage_strength=40.0,
)

binner.fit(df, y="target", column="score", time_col="month")
score_bins = binner.transform(df["score"])
summary = binner.summary()
score_table = binner.score_table()
audit_table = binner.audit_table()

binner.export_binnings_json("artifacts/riskbands_binnings.json")
binner.export_bundle("artifacts/quickstart_run")

binner.plot_bad_rate_over_time(df, y="target", column="score", time_col="month")
binner.plot_bad_rate_heatmap(df, y="target", column="score", time_col="month")
binner.plot_bin_share_over_time(df, y="target", column="score", time_col="month")
binner.plot_score_components(column="score")
```

Fluxo mais amigavel, no estilo sklearn/pandas:

- `fit(df, y="target", column="score", time_col="month")`
- `transform(df)` ou `transform(df["score"])`
- `fit_transform(df["score"], y=df["target"])`
- `binning_table()`, `score_table()`, `audit_table()`, `report()`, `diagnostics()`
- `export_binnings_json()` e `export_bundle()` para auditoria e governanca
- plots diretos para bad rate, heatmap, share temporal e score components
- `get_params()` e `set_params(...)` com aliases como `max_n_bins` e `monotonic_trend`

## Customização do objective

```python
binner = RiskBands(
    strategy="supervised",
    check_stability=True,
    use_optuna=True,
    time_col="month",
    score_strategy="stable",
    score_weights={
        "temporal_variance_weight": 0.18,
        "window_drift_weight": 0.16,
        "rank_inversion_weight": 0.22,
        "separation_weight": 0.24,
        "entropy_weight": 0.08,
        "psi_weight": 0.12,
    },
    normalization_strategy="absolute",
    woe_shrinkage_strength=35.0,
    strategy_kwargs={"n_trials": 10},
)
```

`from riskbands import Binner` remains supported for existing code; new examples prefer `RiskBands`.

Leitura rápida:

- no `standard`, maiores scores continuam melhores
- no `stable`, menores scores são melhores
- relatórios auditáveis expõem score final, componentes raw, componentes normalizados, pesos, estratégia e parâmetros de shrink

## Benchmark principal do repositorio

O benchmark mais importante hoje compara tres lentes:

1. `OptimalBinning` puro como baseline externa
2. `RiskBands` estatico como baseline interna
3. `RiskBands` balanceado/temporal como abordagem orientada a credito

Materiais principais:

- [pd_vintage_benchmark.py](https://github.com/joaaomaia/RiskBands/blob/main/examples/pd_vintage_benchmark/pd_vintage_benchmark.py)
- [pd_vintage_benchmark.ipynb](https://github.com/joaaomaia/RiskBands/blob/main/examples/pd_vintage_benchmark/pd_vintage_benchmark.ipynb)
- [riskbands_synthetic_plotly_comparative_demo.ipynb](https://github.com/joaaomaia/RiskBands/blob/main/examples/riskbands_synthetic_plotly_comparative_demo.ipynb)
- [stable_score_demo.py](https://github.com/joaaomaia/RiskBands/blob/main/examples/stable_score/stable_score_demo.py)
- [pd_vintage_champion_challenger.py](https://github.com/joaaomaia/RiskBands/blob/main/examples/pd_vintage_champion_challenger/pd_vintage_champion_challenger.py)
- [temporal_stability_example.py](https://github.com/joaaomaia/RiskBands/blob/main/examples/temporal_stability/temporal_stability_example.py)

## O que o projeto nao tenta ser

O foco do RiskBands e binning. Ele nao tenta, sozinho, ser:

- pipeline completo de modelagem de PD
- framework de monitoramento de carteira
- solucao completa de MLOps para credito

A proposta e ser uma camada especializada e forte de decisao sobre binning.

## Mensagem principal

O RiskBands nao tenta substituir a forca do `OptimalBinning`.

Ele tenta responder melhor a pergunta que aparece no mundo real de credito:

> Entre os candidatos que parecem bons no agregado, qual continua mais defensavel quando o tempo entra na decisao?
