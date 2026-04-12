# RiskBands

<p align="center">
  <img src="imgs/riskbands_logo_reconstruction_bundle/riskbands_full_lockup.svg" alt="RiskBands" width="340">
</p>

<p align="center">
  Binning para risco de crédito com foco em <strong>robustez temporal</strong>,
  <strong>comparação entre candidatos</strong> e <strong>racional auditável</strong>.
</p>

<p align="center">
  <a href="https://joaaomaia.github.io/RiskBands/">Documentação oficial</a>
  ·
  <a href="https://joaaomaia.github.io/RiskBands/methodology/pd-vintage-benchmark/">Benchmark PD vintage</a>
  ·
  <a href="https://joaaomaia.github.io/RiskBands/technical/quickstart/">Quickstart</a>
  ·
  <a href="https://joaaomaia.github.io/RiskBands/technical/api-overview/">API</a>
</p>

---

## O que é o RiskBands

O RiskBands é uma biblioteca para construir, comparar e auditar candidatos de
binning quando o problema real não é apenas maximizar uma métrica estática, mas
também defender o resultado ao longo do tempo.

Ele foi pensado especialmente para contextos como:

- modelos de **PD**
- scorecards de crédito
- variáveis com **drift temporal**
- leitura relevante por safra ou vintage
- estruturas com bins raros, baixa cobertura ou reversões de ranking

A pergunta central do projeto é simples:

> um binning que parece ótimo no agregado continua defensável quando você abre o comportamento por safra?

## Onde o projeto se diferencia

O `OptimalBinning` já resolve muito bem o problema de corte estático. O
RiskBands não tenta negar isso.

No fluxo supervisionado numérico do repositório atual, o projeto reaproveita
`optbinning.OptimalBinning` no backend do corte estático. O diferencial está no
que vem depois:

- diagnóstico temporal por variável, bin e período
- penalizações estruturais para fragilidade, baixa cobertura e volatilidade
- comparação entre candidatos via `BinComparator`
- score objetivo mais alinhado a trade-offs de risco de crédito
- resumos auditáveis para explicar por que um candidato venceu

Em outras palavras:

- **OptimalBinning puro** ajuda a encontrar um bom corte estático
- **RiskBands** ajuda a decidir se esse corte continua sendo a melhor resposta
  para crédito quando o tempo entra na análise

## Onde o Optuna entra

O projeto também pode usar `Optuna` como camada opcional de busca em fluxos
supervisionados.

O papel do Optuna aqui não é ser o centro da biblioteca. Ele entra quando faz
sentido explorar configurações sob uma régua que já incorpora:

- discriminação estática
- robustez temporal
- cobertura
- bins raros
- reversões de ordenação
- penalizações estruturais e racional auditável

## Quando o RiskBands tende a agregar mais valor

- o IV agregado parece forte, mas a estabilidade no tempo é ruim
- há inversões de event rate entre bins em diferentes safras
- alguns bins somem, ficam raros ou mal cobertos em períodos específicos
- a composição da carteira muda ao longo do tempo
- o time precisa de uma escolha defendível em validação, governança ou comitê

## Quando o estático ainda pode ser suficiente

Nem todo problema exige uma troca de candidato.

Se a variável continua coerente ao longo das safras e a estrutura não mostra
fragilidade relevante, o RiskBands pode simplesmente confirmar que a solução
estática continua sendo a melhor escolha. Isso também é um bom resultado.

## Como começar

### Porta técnica

- [Documentação oficial](https://joaaomaia.github.io/RiskBands/)
- [Instalação](https://joaaomaia.github.io/RiskBands/technical/installation/)
- [Quickstart](https://joaaomaia.github.io/RiskBands/technical/quickstart/)
- [Visão geral da API](https://joaaomaia.github.io/RiskBands/technical/api-overview/)
- [Exemplos](https://joaaomaia.github.io/RiskBands/technical/examples/)

### Porta metodológica

- [Por que RiskBands](https://joaaomaia.github.io/RiskBands/methodology/why-riskbands/)
- [Por que não usar apenas OptimalBinning](https://joaaomaia.github.io/RiskBands/methodology/why-not-only-optimal-binning/)
- [Benchmark PD vintage](https://joaaomaia.github.io/RiskBands/methodology/pd-vintage-benchmark/)
- [Como ler os gráficos](https://joaaomaia.github.io/RiskBands/methodology/how-to-read-the-charts/)
- [Robustez temporal em risco de crédito](https://joaaomaia.github.io/RiskBands/methodology/temporal-robustness-in-credit-risk/)

## Quickstart mínimo

```python
import numpy as np
import pandas as pd

from riskbands import Binner

rng = np.random.default_rng(0)
n = 800

X = pd.DataFrame({"score": rng.normal(size=n)})
X["month"] = rng.choice([202301, 202302, 202303, 202304], size=n)

proba = 0.20 + 0.15 * X["score"] + 0.02 * (X["month"] - 202301)
proba = np.clip(proba, 0.01, 0.99)
y = pd.Series((rng.random(n) < proba).astype(int), name="target")

binner = Binner(
    strategy="supervised",
    check_stability=True,
    monotonic="ascending",
    min_event_rate_diff=0.03,
)

binner.fit(X, y, time_col="month")
summary = binner.temporal_variable_summary(
    diagnostics=binner.temporal_bin_diagnostics(
        X,
        y,
        time_col="month",
        dataset_name="train",
    ),
    time_col="month",
)
```

## Benchmark principal do repositório

O benchmark mais importante hoje compara três lentes:

1. `OptimalBinning` puro como baseline externa
2. `RiskBands` estático como baseline interna
3. `RiskBands` balanceado/temporal como abordagem orientada a crédito

Materiais principais:

- [`examples/pd_vintage_benchmark/pd_vintage_benchmark.py`](examples/pd_vintage_benchmark/pd_vintage_benchmark.py)
- [`examples/pd_vintage_benchmark/pd_vintage_benchmark.ipynb`](examples/pd_vintage_benchmark/pd_vintage_benchmark.ipynb)
- [`examples/pd_vintage_champion_challenger/pd_vintage_champion_challenger.py`](examples/pd_vintage_champion_challenger/pd_vintage_champion_challenger.py)
- [`examples/temporal_stability/temporal_stability_example.py`](examples/temporal_stability/temporal_stability_example.py)

## Instalação

```bash
git clone https://github.com/joaaomaia/RiskBands.git
cd RiskBands
pip install -e .
```

Para desenvolvimento, testes e notebooks:

```bash
pip install -e .[dev]
```

## O que o projeto não tenta ser

O foco do RiskBands é **binning**. Ele não tenta, sozinho, ser:

- pipeline completo de modelagem de PD
- framework de monitoramento de carteira
- solução completa de MLOps para crédito

A proposta é ser uma camada especializada e forte de decisão sobre binning.

## Mensagem principal

O RiskBands não tenta substituir a força do `OptimalBinning`.

Ele tenta responder melhor à pergunta que aparece no mundo real de crédito:

> entre os candidatos que parecem bons no agregado, qual continua mais defensável quando o tempo entra na decisão?
