# NASABinning

<p align="center">
  <img src="./imgs/social_preview.png" alt="NASABinning Banner" width="600"/>
</p>

Biblioteca para binning interpretavel com foco em estabilidade temporal, pensada para cenarios de risco de credito, PD e scorecards.

## O que o projeto faz

O NASABinning ajuda a escolher bins que nao so separam bem no treino, mas continuam defensaveis quando olhamos safras posteriores. O foco do projeto permanece estritamente no seu nucleo:

- binning numerico supervisionado e nao supervisionado
- binning categorico com rare-merge e fallback
- diagnostico temporal por variavel, bin e safra
- otimizacao de binnings com sinais de estabilidade
- reporting auditavel do racional de escolha
- comparacao entre candidatos estaticos, temporais e equilibrados

Ele nao tenta substituir um pipeline completo de PD nem competir com o papel de um framework amplo de risco.

## Quando usar

O NASABinning faz mais sentido quando a pergunta principal e:

- quais bins continuam defensaveis quando saio do treino e olho outras safras
- como comparar uma solucao mais agressiva em IV com outra mais robusta no tempo
- como documentar de forma auditavel por que um binning foi escolhido em um contexto de credito

## Instalacao

Uso basico da biblioteca:

```bash
pip install .
```

Uso para desenvolvimento:

```bash
git clone https://github.com/joaaomaia/NASABinning.git
cd NASABinning
pip install -e .[dev]
```

## Fluxo principal

O fluxo mais importante hoje e:

1. `fit(...)` para ajustar os bins
2. `transform(...)` para obter bins ou WoE
3. `stability_over_time(...)` para o pivot temporal
4. `temporal_bin_diagnostics(...)` para a tabela auditavel por bin/safra
5. `temporal_variable_summary(...)` para o resumo agregado
6. `variable_audit_report(...)` para consolidar o racional da escolha
7. `BinComparator` quando houver champion/challenger entre candidatos

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

print(summary[["variable", "temporal_score", "alert_flags"]])
print(audit_report[["variable", "objective_score", "rationale_summary"]])
```

## Comece por aqui

Se voce esta chegando agora ao projeto:

- veja [docs/index.md](docs/index.md) para a navegacao principal
- veja [examples/README.md](examples/README.md) para o mapa rapido dos exemplos
- rode [examples/temporal_stability/temporal_stability_example.py](examples/temporal_stability/temporal_stability_example.py) para entender o fluxo base
- rode [examples/pd_vintage_champion_challenger/pd_vintage_champion_challenger.py](examples/pd_vintage_champion_challenger/pd_vintage_champion_challenger.py) para o exemplo ancora de credito/PD com vintages

## Exemplo ancora para credito / PD

O exemplo mais importante do repositorio agora vive em uma pasta propria, com versao Python e notebook:

- [examples/pd_vintage_champion_challenger/pd_vintage_champion_challenger.py](examples/pd_vintage_champion_challenger/pd_vintage_champion_challenger.py)
- [examples/pd_vintage_champion_challenger/pd_vintage_champion_challenger.ipynb](examples/pd_vintage_champion_challenger/pd_vintage_champion_challenger.ipynb)

Ele usa material de apoio em `research/raw_material/` para montar um fluxo de credito enxuto com `bureau_score`, `month`, `risk_segment` e `target`. Em particular:

- `credit_data_synthesizer.py` gera o painel sintetico de vintages
- `credit_data_sampler.py` entra como preview opcional de rebalanceamento por safra

O champion/challenger principal continua rodando sobre o painel bruto para preservar a tensao entre discriminacao e estabilidade:

- campeao estatico: maior forca em discriminacao
- campeao temporal: melhor leitura no perfil temporal agregado
- campeao equilibrado: melhor compromisso entre poder e robustez

Isso ajuda a mostrar um ponto central em credito: melhor treino nem sempre e o melhor binning para PD.

## Superficie publica principal

O pacote agora expõe diretamente:

```python
from nasabinning import (
    NASABinner,
    BinComparator,
    temporal_separability_score,
    ks_over_time,
    psi_over_time,
)
```

## Validacao rapida

Validacao local enxuta:

```bash
pytest -q --basetemp .pytest_tmp
```

O repositorio agora tambem inclui workflow leve de CI em [tests.yml](.github/workflows/tests.yml).

## Mapa do repositorio

- [docs/index.md](docs/index.md): ponto de entrada da documentacao
- [docs/api_reference.md](docs/api_reference.md): contrato principal da API
- [examples/README.md](examples/README.md): mapa dos exemplos
- [examples/temporal_stability](examples/temporal_stability): quickstart temporal
- [examples/pd_vintage_champion_challenger](examples/pd_vintage_champion_challenger): exemplo ancora de credito

## Licenca

Distribuido sob a licenca MIT. Veja [LICENSE](LICENSE).
