# NASABinning

Biblioteca para binning interpretavel com foco em estabilidade temporal, pensada para cenarios de risco de credito, PD e scorecards.

## Visao geral

O NASABinning prioriza a qualidade temporal dos bins, e nao apenas a separacao estatica em uma unica amostra. A biblioteca combina:

- binning supervisionado com `OptimalBinning`
- binning numerico nao supervisionado com `KBinsDiscretizer`
- binning categorico com rare-merge e fallback seguro
- metricas classicas como IV e PSI
- diagnosticos de estabilidade ao longo das safras
- otimizacao com Optuna para buscar bins mais estaveis no tempo

No fluxo temporal, a ideia central e privilegiar bins que mantenham curvas de `event rate` separadas e consistentes entre safras, abrindo caminho para usos mais robustos em treino, validacao temporal e OOT.

## Estado atual do core

O core atual cobre:

- `fit -> transform` para variaveis numericas e categoricas
- `stability_over_time(...)` para gerar o pivot temporal por bin e safra
- `plot_event_rate_stability(...)` para inspecao visual
- `save_report(...)` para export simples em `.xlsx` ou `.json`
- `temporal_separability_score(...)` como metrica de separacao temporal robusta a esparsidade

Importante:

- `time_col` e usada como coluna de safra e fica fora do conjunto de features binadas
- o caminho com Optuna esta suportado para `strategy="supervised"`
- a API principal de resumo de bins foi unificada em `bin_summary`

## Instalacao para desenvolvimento

Enquanto o empacotamento do projeto nao e finalizado, use o fluxo abaixo:

```bash
git clone https://github.com/seu-usuario/NASABinning.git
cd NASABinning
pip install -r requirements.txt
```

## Exemplo rapido

```python
import numpy as np
import pandas as pd

from nasabinning import NASABinner

rng = np.random.default_rng(0)
n = 800

X = pd.DataFrame({"score": rng.normal(size=n)})
X["AnoMesReferencia"] = rng.choice([202301, 202302, 202303, 202304], size=n)

proba = 0.20 + 0.15 * X["score"] + 0.02 * (X["AnoMesReferencia"] - 202301)
proba = np.clip(proba, 0.01, 0.99)
y = pd.Series((rng.random(n) < proba).astype(int), name="target")

binner = NASABinner(
    strategy="supervised",
    min_event_rate_diff=0.03,
    check_stability=True,
    monotonic="ascending",
    use_optuna=False,
)

binner.fit(X, y, time_col="AnoMesReferencia")
X_woe = binner.transform(X, return_woe=True)

pivot = binner.stability_over_time(X, y, time_col="AnoMesReferencia")
binner.plot_event_rate_stability(pivot)
binner.save_report("reports/binning_report.xlsx")

print(binner.bin_summary.head())
print(binner.iv_)
```

## Exemplo com Optuna

```python
from nasabinning import NASABinner

binner = NASABinner(
    strategy="supervised",
    check_stability=True,
    use_optuna=True,
    strategy_kwargs={"n_trials": 20},
)

binner.fit(X, y, time_col="AnoMesReferencia")
pivot = binner.stability_over_time(X, y, time_col="AnoMesReferencia")
print(binner.best_params_)
```

## Estrutura principal

```text
nasabinning/
|-- binning_engine.py
|-- temporal_stability.py
|-- refinement.py
|-- metrics.py
|-- reporting.py
|-- compare.py
|-- visualizations.py
`-- strategies/
```

## Proximo foco

O proximo passo natural do projeto e a camada de diagnostico por safra, com metricas por variavel e por bin, voltadas a:

- event rate por safra
- share do bin no tempo
- volatilidade temporal
- WoE e contribuicao de IV por periodo
- sinais de degradacao e reversao de ranking

## Licenca

Distribuido sob a licenca MIT. Veja [LICENSE](LICENSE).
