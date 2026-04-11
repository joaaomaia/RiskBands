# RiskBands

<p align="center">
  <img src="./imgs/social_preview.png" alt="Banner do RiskBands" width="600"/>
</p>

Binning interpretável para risco de crédito, PD e fluxos de scorecard, com atenção explícita à estabilidade temporal.

## O que o RiskBands resolve

Um binning estático pode parecer forte em desenvolvimento e, ainda assim, se tornar difícil de defender quando as vintages mudam. O RiskBands ajuda equipes a avaliar os bins não apenas pela discriminação, mas também por quão estáveis, auditáveis e estruturalmente robustos eles permanecem ao longo do tempo.

A biblioteca permanece intencionalmente focada na camada de binning:

- binning numérico supervisionado e não supervisionado
- binning categórico com tratamento de categorias raras
- diagnósticos temporais por variável, bin e período
- comparação de candidatos para perfis estáticos, temporais e balanceados
- reporte auditável da justificativa da seleção final

Não é um framework completo de modelagem de PD. É a camada de binning e estabilidade que pode se encaixar dentro de um fluxo mais amplo de crédito.

## Por que a estabilidade temporal importa

Um processo de binning puramente estático otimiza a separação na amostra de desenvolvimento. Em risco de crédito, isso muitas vezes não é suficiente. A composição dos períodos, a estratégia de originação e a qualidade dos dados podem mudar, então um binning que parece excelente no treino pode se degradar em vintages posteriores.

O RiskBands foi projetado para cenários em que precisamos perguntar:

- os bins mantêm sua ordenação ao longo do tempo?
- as taxas de evento permanecem separadas entre os períodos?
- alguns bins estão ficando esparsos ou estruturalmente frágeis?
- conseguimos explicar por que um candidato venceu para além do IV bruto?

## Instalação

```bash
pip install .
```

Para desenvolvimento:

```bash
git clone https://github.com/joaaomaia/RiskBands.git
cd RiskBands
pip install -e .[dev]
```

## API principal

```python
from riskbands import Binner, BinComparator
from riskbands.temporal_stability import ks_over_time
```

O pacote público agora expõe:

- pacote: `riskbands`
- classe principal: `Binner`

## Fluxo principal

1. Ajuste o binner com `Binner(...).fit(X, y, time_col=...)`.
2. Transforme o conjunto de features com `transform(...)`.
3. Construa pivôs temporais com `stability_over_time(...)`.
4. Abra os diagnósticos detalhados com `temporal_bin_diagnostics(...)`.
5. Resuma o comportamento no nível da variável com `temporal_variable_summary(...)`.
6. Consolide a trilha de auditoria com `variable_audit_report(...)`.
7. Compare candidatos com `BinComparator` ao fazer análises champion/challenger.

## Exemplo rápido

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

diagnostics = binner.temporal_bin_diagnostics(
    X,
    y,
    time_col="month",
    dataset_name="train",
)
summary = binner.temporal_variable_summary(
    diagnostics=diagnostics,
    time_col="month",
)
audit_report = binner.variable_audit_report(
    X,
    y,
    time_col="month",
    dataset_name="train",
)

print(summary[["variable", "temporal_score", "alert_flags"]])
print(audit_report[["variable", "objective_score", "rationale_summary"]])
```

## Exemplos

- [examples/pd_vintage_benchmark/pd_vintage_benchmark.py](examples/pd_vintage_benchmark/pd_vintage_benchmark.py)
  Benchmark visual comparando `OptimalBinning` puro versus RiskBands em cenarios de credito com drift temporal.
- [examples/pd_vintage_benchmark/pd_vintage_benchmark.ipynb](examples/pd_vintage_benchmark/pd_vintage_benchmark.ipynb)
  Notebook premium da vitrine metodologica, com board comparativo, curvas por vintage e heatmaps.

- [examples/temporal_stability/temporal_stability_example.py](examples/temporal_stability/temporal_stability_example.py)
  Quickstart do fluxo temporal.
- [examples/pd_vintage_champion_challenger/pd_vintage_champion_challenger.py](examples/pd_vintage_champion_challenger/pd_vintage_champion_challenger.py)
  Exemplo orientado a crédito com análise champion/challenger por vintages.
- [examples/README.md](examples/README.md)
  Mapa do conjunto de exemplos.

## Histórico de breaking changes

Este código passou por duas simplificações deliberadas de API:

- `NASABinning` -> `RiskBands`
- `RiskBandsBinner` -> `Binner`

O construtor oficial atual é `Binner`.

## Migração

Se você já estava no namespace `riskbands`, mas ainda usava o nome mais longo da classe:

```python
# antes
from riskbands import RiskBandsBinner

# agora
from riskbands import Binner
```

Se você ainda importa `nasabinning`, também precisa migrar para `riskbands`.

Veja [docs/migration.md](docs/migration.md) para as notas completas de migração.

## Documentação

- [docs/index.md](docs/index.md)
- [docs/api_reference.md](docs/api_reference.md)
- [docs/migration.md](docs/migration.md)

## Validação

```bash
pytest -q --basetemp .pytest_tmp
python -m build
```

O CI está definido em [tests.yml](.github/workflows/tests.yml).

## Licença

MIT. Veja [LICENSE](LICENSE).
