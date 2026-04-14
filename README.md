# RiskBands

Binning para risco de credito com foco em robustez temporal, comparacao entre
candidatos e racional auditavel.

[Documentacao oficial](https://joaaomaia.github.io/RiskBands/) |
[Benchmark PD vintage](https://joaaomaia.github.io/RiskBands/methodology/pd-vintage-benchmark/) |
[Quickstart](https://joaaomaia.github.io/RiskBands/technical/quickstart/) |
[API](https://joaaomaia.github.io/RiskBands/technical/api-overview/)

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

- `legacy`
  Mantém o objetivo histórico baseado em componentes positivos menos penalidades.
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

Para desenvolvimento, testes e notebooks:

```bash
git clone https://github.com/joaaomaia/RiskBands.git
cd RiskBands
pip install -e .[dev]
```

## Como comecar

Porta tecnica:

- [Instalacao](https://joaaomaia.github.io/RiskBands/technical/installation/)
- [Quickstart](https://joaaomaia.github.io/RiskBands/technical/quickstart/)
- [Visao geral da API](https://joaaomaia.github.io/RiskBands/technical/api-overview/)
- [Exemplos](https://joaaomaia.github.io/RiskBands/technical/examples/)

Porta metodologica:

- [Por que RiskBands](https://joaaomaia.github.io/RiskBands/methodology/why-riskbands/)
- [Por que nao usar apenas OptimalBinning](https://joaaomaia.github.io/RiskBands/methodology/why-not-only-optimal-binning/)
- [Benchmark PD vintage](https://joaaomaia.github.io/RiskBands/methodology/pd-vintage-benchmark/)
- [Como ler os graficos](https://joaaomaia.github.io/RiskBands/methodology/how-to-read-the-charts/)
- [Robustez temporal em risco de credito](https://joaaomaia.github.io/RiskBands/methodology/temporal-robustness-in-credit-risk/)

## Quickstart minimo

```python
import numpy as np
import pandas as pd

from riskbands import Binner

rng = np.random.default_rng(0)
n = 800

df = pd.DataFrame({"score": rng.normal(size=n)})
df["month"] = rng.choice([202301, 202302, 202303, 202304], size=n)

proba = 0.20 + 0.15 * df["score"] + 0.02 * (df["month"] - 202301)
proba = np.clip(proba, 0.01, 0.99)
df["target"] = (rng.random(n) < proba).astype(int)

binner = Binner(
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
score_details = binner.score_details()
diagnostics = binner.diagnostics(kind="bin")
```

Fluxo mais amigavel, no estilo sklearn/pandas:

- `fit(df, y="target", column="score", time_col="month")`
- `transform(df)` ou `transform(df["score"])`
- `fit_transform(df["score"], y=df["target"])`
- `binning_table()`, `summary()`, `report()`, `score_details()`, `diagnostics()`
- `get_params()` e `set_params(...)` com aliases como `max_n_bins` e `monotonic_trend`

## Customização do objective

```python
binner = Binner(
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

Leitura rápida:

- no `legacy`, maiores scores continuam melhores
- no `stable`, menores scores são melhores
- relatórios auditáveis expõem score final, componentes raw, componentes normalizados, pesos, estratégia e parâmetros de shrink

## Benchmark principal do repositorio

O benchmark mais importante hoje compara tres lentes:

1. `OptimalBinning` puro como baseline externa
2. `RiskBands` estatico como baseline interna
3. `RiskBands` balanceado/temporal como abordagem orientada a credito

Materiais principais:

- [pd_vintage_benchmark.py](https://github.com/joaaomaia/RiskBands/blob/master/examples/pd_vintage_benchmark/pd_vintage_benchmark.py)
- [pd_vintage_benchmark.ipynb](https://github.com/joaaomaia/RiskBands/blob/master/examples/pd_vintage_benchmark/pd_vintage_benchmark.ipynb)
- [riskbands_synthetic_plotly_comparative_demo.ipynb](https://github.com/joaaomaia/RiskBands/blob/master/examples/riskbands_synthetic_plotly_comparative_demo.ipynb)
- [stable_score_demo.py](https://github.com/joaaomaia/RiskBands/blob/master/examples/stable_score/stable_score_demo.py)
- [pd_vintage_champion_challenger.py](https://github.com/joaaomaia/RiskBands/blob/master/examples/pd_vintage_champion_challenger/pd_vintage_champion_challenger.py)
- [temporal_stability_example.py](https://github.com/joaaomaia/RiskBands/blob/master/examples/temporal_stability/temporal_stability_example.py)

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
