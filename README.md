# NASABinning

<p align="center">
  <img src="./imgs/social_preview.png" alt="NASABinning Banner" width="600"/>
</p>

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

## Casos de uso prioritarios

O NASABinning faz mais sentido quando a pergunta principal e:

- quais bins continuam defensaveis quando saio do treino e olho outras safras
- como comparar uma solucao mais agressiva em IV com outra mais robusta no tempo
- como documentar de forma auditavel por que um binning foi escolhido em um contexto de credito

Ele nao tenta substituir um pipeline completo de PD. O foco continua sendo a escolha, diagnostico, comparacao e explicacao de bins.

## Comece por aqui

Se voce esta chegando agora ao projeto:

- veja [examples/README.md](examples/README.md) para o mapa rapido dos exemplos
- rode [examples/temporal_stability_example.py](examples/temporal_stability_example.py) para entender o fluxo base
- rode [examples/pd_vintage_champion_challenger.py](examples/pd_vintage_champion_challenger.py) para o exemplo ancora de credito/PD com vintages

## Estado atual do core

O core atual cobre:

- `fit -> transform` para variaveis numericas e categoricas
- `stability_over_time(...)` para gerar o pivot temporal por bin e safra
- `temporal_bin_diagnostics(...)` para tabela auditavel por variavel/bin/safra
- `temporal_variable_summary(...)` para resumo agregado com alertas de estabilidade
- `variable_audit_report(...)` para consolidar cortes, metricas, penalizacoes e racional por variavel
- `plot_event_rate_stability(...)` para inspecao visual
- `save_report(...)` para export simples em `.xlsx` ou `.json`
- `temporal_separability_score(...)` como metrica de separacao temporal robusta a esparsidade
- objetivo de otimizacao com penalizacoes de estabilidade, rareza e perda de ordenacao
- comparacao de candidatos com `BinComparator` em perfis estatico, temporal e equilibrado

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
diagnostics = binner.temporal_bin_diagnostics(
    X,
    y,
    time_col="AnoMesReferencia",
    dataset_name="train",
)
summary = binner.temporal_variable_summary(
    diagnostics=diagnostics,
    time_col="AnoMesReferencia",
)
audit_report = binner.variable_audit_report(
    X,
    y,
    time_col="AnoMesReferencia",
    dataset_name="train",
)

binner.plot_event_rate_stability(pivot)
binner.save_report("reports/binning_report.xlsx")

print(binner.bin_summary.head())
print(diagnostics.head())
print(summary[["variable", "temporal_score", "alert_flags"]])
print(audit_report[["variable", "objective_score", "key_penalties", "rationale_summary"]])
print(binner.iv_)
```

## Exemplo com Optuna

```python
from nasabinning import NASABinner

binner = NASABinner(
    strategy="supervised",
    check_stability=True,
    use_optuna=True,
    strategy_kwargs={
        "n_trials": 20,
        "objective_kwargs": {
            "minimums": {"iv": 0.05, "coverage_ratio": 0.75},
        },
    },
)

binner.fit(X, y, time_col="AnoMesReferencia")
pivot = binner.stability_over_time(X, y, time_col="AnoMesReferencia")
print(binner.best_params_)
print(binner.objective_summaries_)
```

## Exemplo ancora para credito / PD

O exemplo mais importante do repositório agora e:

- [examples/pd_vintage_champion_challenger.py](examples/pd_vintage_champion_challenger.py)

Ele mostra um fluxo champion/challenger em cima de uma variavel de risco com multiplas safras, comparando um pequeno pool de candidatos:

- campeao estatico: maior forca em discriminacao
- campeao temporal: melhor leitura no perfil temporal agregado
- campeao equilibrado: melhor compromisso entre poder e robustez

O ponto central do exemplo e mostrar que:

- bins raros e reversoes podem sinalizar fragilidade
- melhor treino nem sempre e o melhor binning para credito
- a decisao final precisa olhar discriminacao junto com estabilidade temporal

## Reporting auditavel e comparacao

O NASABinning agora consegue explicar melhor por que um binning venceu, sem sair do
escopo de binning e estabilidade temporal.

O report consolidado por variavel combina:

- cortes finais (`cut_summary`)
- metricas estaticas como `iv` e `ks`
- metricas temporais como `temporal_score`, cobertura e volatilidade
- componentes e penalizacoes do objetivo
- `alert_flags`, `key_penalties` e `rationale_summary`

Para comparar candidatos, use `BinComparator`:

```python
from nasabinning.compare import BinComparator

configs = [
    {"name": "static_candidate", "strategy": "supervised", "max_bins": 6},
    {"name": "stable_candidate", "strategy": "unsupervised", "method": "quantile", "n_bins": 4},
]

cmp = BinComparator(configs, time_col="AnoMesReferencia")
cmp.fit_compare(X, y)

candidate_audit = cmp.candidate_audit_report()
profiles = cmp.candidate_profile_summary()
winners = cmp.winner_summary()

print(candidate_audit[["candidate_name", "variable", "objective_score", "rationale_summary"]])
print(winners[["variable", "best_static_candidate", "best_temporal_candidate", "selected_candidate"]])
```

## Como ler champion / challenger em credito

Uma leitura pratica do comparador e:

- `best_static_candidate`: o candidato que mais impressiona em discriminacao
- `best_temporal_candidate`: o candidato com melhor leitura temporal agregada
- `best_balanced_candidate`: o candidato que melhor equilibra poder e robustez
- `selected_candidate`: a recomendacao final dentro daquele conjunto de candidatos

Em um contexto de PD, a escolha final nem sempre deve seguir o campeao estatico. Se a estabilidade temporal virar uma preocupacao material, o challenger temporal pode ser a opcao mais prudente, mesmo com menos brilho no treino.

## Estrutura principal

```text
nasabinning/
|-- binning_engine.py
|-- temporal_stability.py
|-- temporal_diagnostics.py
|-- refinement.py
|-- metrics.py
|-- reporting.py
|-- compare.py
|-- visualizations.py
`-- strategies/
```

## Proximo foco

O proximo passo natural do projeto e consolidar maturidade final de pacote:

- documentacao mais polida e navegavel
- organizacao final de exemplos e API
- empacotamento e preparo para uso mais estavel
- smoke tests e CI mais claros

## Otimizacao orientada a credito

O objetivo atual do Optuna continua estritamente no escopo do NASABinning:
ele nao tenta virar um framework de modelagem de risco, mas passa a escolher
bins de forma mais alinhada com PD.

A funcao-objetivo agora combina:

- separacao estatica e IV como sinais-base
- `temporal_score` como sinal positivo de estabilidade
- penalizacoes por bins raros
- penalizacoes por baixa cobertura temporal
- penalizacoes por volatilidade de `event_rate`, `WoE` e `bin_share`
- penalizacoes por quebra de monotonicidade e reversao de ranking

Isso ajuda a evitar binnings que parecem fortes no treino, mas degradam mais no tempo.

## Licenca

Distribuido sob a licenca MIT. Veja [LICENSE](LICENSE).
