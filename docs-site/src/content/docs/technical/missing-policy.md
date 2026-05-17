---
title: "Missing policy"
description: "Como usar standard, separate_bin e forbid para tratar missing values de forma auditavel no RiskBands."
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

`legacy` pode aparecer em metadados antigos como compatibilidade, mas nao e
recomendacao nova. O nome canonico atual e `standard`.

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

```python
from riskbands.reporting import load_bundle

binner.export_bundle("riskbands_bundle")
bundle = load_bundle("riskbands_bundle")

print(bundle["missing_policy"])
print(bundle["missing_profile"])
```

Bundles antigos sem esses campos continuam carregando como `standard`.

## O que nao esta implementado

Esta pagina documenta o contrato atual. Ela nao anuncia novas features.

Ainda nao existem:

- merge policies auditaveis para unir o bin missing a outro bin;
- imputacao inteligente dentro do RiskBands;
- similaridade comportamental automatica para missing;
- fitting estatistico totalmente distribuido em Spark.

O RiskBands ajuda a tornar a decisao defensavel e auditavel, mas nao garante
conformidade regulatoria automaticamente.
