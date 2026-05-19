---
title: "Missing policy"
description: "Como usar standard, separate_bin, forbid e merge para tratar missing values de forma auditavel no RiskBands."
---

## Ideia central

Em risco de credito, missing values podem carregar sinal proprio. Um campo
ausente pode refletir origem de dados, canal, politica operacional ou mudanca
de captura. Por isso, aplicar `fillna(...)` silencioso antes do binning pode
esconder uma decisao relevante.

`missing_policy` torna essa decisao explicita:

```python
from riskbands import RiskBands

binner = RiskBands(missing_policy="separate_bin")
```

## Politicas

| Politica | O que faz | Quando usar |
| --- | --- | --- |
| `standard` | Preserva o comportamento compativel atual. | Reproducao de fluxos existentes e compatibilidade. |
| `separate_bin` | Cria bin explicito `Missing` para missing nas features selecionadas. | Analise auditavel de missing como grupo proprio. |
| `forbid` | Falha em `fit` ou `transform` quando encontra missing. | Governanca que exige tratamento upstream antes do binning. |
| `merge` | Aprende no `fit` um bin regular de destino para o grupo missing. | Quando missing deve ser auditado, mas roteado para o bin mais parecido. |

`legacy` pode aparecer em metadados antigos como compatibilidade, mas nao e
recomendacao nova. O nome canonico atual e `standard`.

## Merge auditavel

`missing_policy="merge"` e opt-in e exige um criterio explicito:

```python
binner = RiskBands(
    missing_policy="merge",
    missing_merge_criterion="nearest_event_rate",
    missing_merge_fallback="separate_bin",
)
```

```python
binner = RiskBands(
    missing_policy="merge",
    missing_merge_criterion="nearest_woe",
    missing_merge_fallback="raise",
)
```

`nearest_event_rate` escolhe o bin regular com menor distancia absoluta de taxa
de evento em relacao ao grupo missing no fit. `nearest_woe` usa a menor
distancia absoluta de WoE no mesmo perfil de fit.

O merge nao e imputacao opaca. A decisao fica em `missing_decision_log_`, os
candidatos ficam em `missing_merge_candidates_`, e o mapa aprendido fica em
`missing_merge_map_`. O `transform(...)` usa apenas essa decisao aprendida no
fit; ele nao aprende regra nova com a base de aplicacao.

## Exemplo pandas

O script completo esta em
[`examples/missing_policy/missing_policy_pandas_demo.py`](https://github.com/joaaomaia/RiskBands/blob/main/examples/missing_policy/missing_policy_pandas_demo.py).

```python
import numpy as np
import pandas as pd

from riskbands import RiskBands

df = pd.DataFrame(
    {
        "score": [410.0, 450.0, np.nan, 620.0, 710.0] * 6,
        "rating": ["A", "B", None, "C", "D"] * 6,
        "target": [0, 0, 1, 1, 1] * 6,
    }
)

binner = RiskBands(
    max_bins=4,
    min_event_rate_diff=0.0,
    force_categorical=["rating"],
    missing_policy="separate_bin",
)

binner.fit(df, y="target", columns=["score", "rating"], validate=True)
df_binned = binner.transform(df[["score", "rating"]], validate=True)

print(df_binned.head())
print(binner.missing_profile_)
print(binner.missing_decision_log_)
```

Rodar localmente:

```bash
python examples/missing_policy/missing_policy_pandas_demo.py
```

## Exemplo PySpark

PySpark e extra opcional. A instalacao base nao instala Spark.

```bash
pip install "riskbands[spark]"
```

O script completo esta em
[`examples/missing_policy/missing_policy_pyspark_demo.py`](https://github.com/joaaomaia/RiskBands/blob/main/examples/missing_policy/missing_policy_pyspark_demo.py).

Ele usa:

- `SparkSession` local pequena com `local[2]`;
- `spark.sql.shuffle.partitions=2`;
- dataset sintetico pequeno;
- `missing_policy="separate_bin"`;
- `transform(validate=True)`;
- `missing_policy="forbid"` gerando erro claro;
- nenhum UDF.

```bash
python examples/missing_policy/missing_policy_pyspark_demo.py
```

Se PySpark nao estiver instalado, o exemplo avisa como instalar o extra e sai
sem tornar Spark uma dependencia base.

## O que inspecionar

Apos `fit(...)`, olhe:

- `missing_policy_`
- `effective_missing_policy_`
- `missing_profile_`
- `missing_decision_log_`
- `fit_profile_`, `reference_profile_` e `application_profile_` quando houver
  validacao.

`missing_profile_` mostra volume, share, eventos, event rate, backend, contexto
e se a linha representa bin missing. `missing_decision_log_` registra a acao
tomada por variavel.

## Bundle e reporting

`export_bundle(...)` persiste a trilha de missing values:

- `missing_policy`
- `effective_missing_policy`
- `missing_profile`
- `missing_decision_log`
- `missing_merge_criterion`
- `missing_merge_fallback`
- `missing_merge_candidates`
- `missing_merge_map`

```python
from riskbands.reporting import load_bundle

binner.export_bundle("riskbands_bundle")
bundle = load_bundle("riskbands_bundle")

print(bundle["missing_policy"])
print(bundle["missing_profile"])
```

Bundles antigos sem esses campos continuam carregando como `standard`.

## O que nao esta implementado

Esta pagina documenta o contrato atual. Ainda nao existem:

- `temporal_stable` como criterio de merge;
- `monotonic_neighbor` como criterio de merge;
- criterios de merge alem de `nearest_event_rate` e `nearest_woe`;
- PySpark merge completo;
- imputacao inteligente dentro do RiskBands;
- fitting estatistico totalmente distribuido em Spark.

O RiskBands ajuda a tornar a decisao defensavel e auditavel, mas nao garante
conformidade regulatoria automaticamente.
