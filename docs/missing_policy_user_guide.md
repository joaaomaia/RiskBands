# Missing policy user guide

Este guia explica como usar `missing_policy` no RiskBands em fluxos pandas e
PySpark, com foco em risco de credito, auditabilidade e revisao defensavel do
binning. Ele reflete a preparacao da v2.3.0 para merge auditavel de missing
values, sem afirmar publicacao.

## Por que missing values importam

Em risco de credito, valores ausentes raramente sao apenas "sujeira" estatistica.
Um campo missing pode indicar falta de documentacao, origem diferente do cliente,
produto novo, falha operacional, canal de captura incompleto ou mudanca de
politica. Por isso, substituir missing values silenciosamente com `fillna(...)`
antes do binning pode esconder um comportamento relevante.

O RiskBands trata missing values como parte do contrato auditavel do binning. A
decisao deve ficar visivel para quem revisa o modelo, para quem monitora drift e
para quem precisa explicar por que determinado bin foi mantido, isolado ou
bloqueado.

## Politicas disponiveis

Use `missing_policy` ao criar o `RiskBands`:

```python
from riskbands import RiskBands

binner = RiskBands(missing_policy="separate_bin")
```

Valores aceitos:

| Politica | Comportamento | Quando usar | Observacao |
| --- | --- | --- | --- |
| `standard` | Preserva o comportamento compativel atual. | Quando voce precisa manter compatibilidade com fluxos existentes. | E o default. |
| `separate_bin` | Cria um bin explicito `Missing` quando ha missing nas features selecionadas. | Quando missing pode carregar sinal de risco e precisa aparecer no reporting. | Recomendado para analise auditavel de missing. |
| `forbid` | Falha em `fit` ou `transform` se houver missing nas features selecionadas. | Quando a governanca exige que dados ausentes sejam tratados antes do binning. | Nao corrige os dados; bloqueia o fluxo. |
| `merge` | Aprende no `fit` um bin regular de destino para o grupo missing. | Quando missing deve ser auditado, mas roteado para o bin mais parecido. | Requer `missing_merge_criterion`. |

`legacy` nao e recomendacao nova para `missing_policy`. Quando aparecer em
metadados antigos, ele e tratado como compatibilidade historica e normalizado
para `standard`.

## `standard`

`standard` e o default. Ele conserva a semantica existente da biblioteca para
evitar quebra em usuarios atuais.

```python
binner = RiskBands(
    max_bins=4,
    missing_policy="standard",
)
```

Use quando:

- voce esta reproduzindo um fluxo ja aprovado;
- quer comparar v2.2.x com uma execucao anterior;
- ainda nao decidiu se missing deve ser explicitado como grupo proprio.

Mesmo em `standard`, os campos de auditoria registram a politica efetiva e a
decisao tomada quando missing values sao encontrados.

## `separate_bin`

`separate_bin` torna missing values explicitos como `Missing`. Isso evita que o
analista perca de vista o volume, a taxa de evento e o peso do missing no
resultado.

```python
binner = RiskBands(
    max_bins=4,
    force_categorical=["rating"],
    missing_policy="separate_bin",
)

binner.fit(df, y="target", columns=["score", "rating"], validate=True)
df_binned = binner.transform(df[["score", "rating"]], validate=True)
```

Use quando:

- missing pode representar comportamento de risco proprio;
- voce precisa mostrar share, event rate ou WoE do missing;
- o bundle precisa guardar uma trilha explicita da decisao;
- o time de model risk quer revisar se missing deve ficar separado no scorecard.

Essa politica nao faz imputacao opaca. Ela separa missing como bin observavel.

## `merge`

`merge` e uma politica opt-in para pandas. Ela primeiro trata missing como grupo
observavel no `fit`, depois escolhe um bin regular de destino com criterio
explicito e auditavel.

```python
binner = RiskBands(
    max_bins=4,
    missing_policy="merge",
    missing_merge_criterion="nearest_event_rate",
    missing_merge_fallback="separate_bin",
)
```

Os criterios suportados sao:

- `nearest_event_rate`: escolhe o bin regular cuja taxa de evento no fit fica
  mais perto da taxa de evento do grupo missing.
- `nearest_woe`: escolhe o bin regular cujo WoE no fit fica mais perto do WoE
  do grupo missing.

Use `nearest_event_rate` quando a revisao quer explicar a decisao em termos de
taxa de evento observada. Use `nearest_woe` quando a similaridade do scorecard
deve seguir a escala WoE ja usada no binner.

`missing_merge_fallback` controla missing que aparece no `transform` sem uma
decisao aprendida no `fit`:

- `separate_bin`: retorna `Missing` para esses valores.
- `raise`: falha com erro claro.

O `transform(...)` nunca aprende uma nova regra de merge. Ele usa apenas
`missing_merge_map_`, aprendido no `fit`, e nao usa target, event rate, WoE ou
distribuicao da base de aplicacao para retargeting.

Com `return_woe=True`, missing values roteados por merge recebem o WoE do bin de
destino aprendido. Se nao houve destino aprendido e o fallback gerou `Missing`,
nao ha WoE ajustado para esse novo label e o metodo falha com erro claro.

## `forbid`

`forbid` e uma politica de governanca. Ela interrompe o fluxo quando missing
values chegam a uma feature selecionada.

```python
binner = RiskBands(missing_policy="forbid")
binner.fit(df, y="target", column="score")
```

Se `score` tiver missing, o `fit` falha com erro claro. O mesmo vale para
`transform(...)`: um binner ajustado com `forbid` tambem falha quando a base de
aplicacao contem missing nas features selecionadas.

Use quando:

- a origem de dados deve garantir completude antes do binning;
- missing deve ser tratado por uma etapa upstream documentada;
- a regra de producao nao aceita missing em variaveis criticas.

## Exemplo pandas

O exemplo completo esta em
`examples/missing_policy/missing_policy_pandas_demo.py`.

Resumo:

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

O mesmo exemplo tambem roda `missing_policy="merge"` com
`missing_merge_criterion="nearest_event_rate"` e
`missing_merge_criterion="nearest_woe"`, imprime `missing_merge_candidates_` e
faz roundtrip de bundle para confirmar persistencia dos campos de merge.

## Exemplo PySpark

O exemplo completo esta em
`examples/missing_policy/missing_policy_pyspark_demo.py`.

PySpark e opcional. A instalacao base do RiskBands nao instala Spark. Use:

```bash
pip install "riskbands[spark]"
```

Fluxo resumido:

```python
from riskbands import RiskBands

binner = RiskBands(
    max_bins=4,
    min_event_rate_diff=0.0,
    force_categorical=["rating"],
    missing_policy="separate_bin",
    sample_size=1000,
)

binner.fit(spark_df, y="target", columns=["score", "rating"], validate=True)
spark_binned = binner.transform(
    spark_df.select("score", "rating"),
    columns=["score", "rating"],
    validate=True,
)
```

O exemplo usa `SparkSession` local pequena, `spark.sql.shuffle.partitions=2`,
nao usa UDF e coleta apenas uma amostra pequena para demonstracao.

## Como inspecionar a trilha

Apos `fit(...)`, os principais campos sao:

- `missing_policy_`: politica solicitada e normalizada.
- `effective_missing_policy_`: politica efetivamente aplicada.
- `missing_profile_`: linhas com volume, share, eventos, event rate, backend,
  contexto e indicacao de bin missing.
- `missing_decision_log_`: decisao por variavel, acao tomada e observacoes.
- `fit_profile_`, `source_profile_`, `reference_profile_` e
  `application_profile_`: perfis usados em validacao e monitoramento.

Exemplo:

```python
profile = binner.missing_profile_
decisions = binner.missing_decision_log_
```

## Bundle e reporting

`export_bundle(...)` persiste os campos de missing policy quando disponiveis:

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

Bundles antigos sem esses campos continuam carregando como `standard` para
compatibilidade.

## O que ainda nao existe

Na preparacao v2.3.0, o escopo e propositalmente estreito. Ainda nao existem:

- `temporal_stable` como criterio de merge;
- `monotonic_neighbor` como criterio de merge;
- criterios de merge alem de `nearest_event_rate` e `nearest_woe`;
- PySpark merge completo;
- imputacao inteligente dentro do RiskBands;
- backend Spark distribuido completo para o fitting estatistico.

Esses itens devem ser tratados como pesquisa ou trabalho futuro, nunca como
funcionalidade disponivel.

## Cuidados regulatorios

Use linguagem de defensabilidade e auditabilidade. O RiskBands ajuda a tornar a
decisao de missing values explicita, rastreavel e revisavel, mas isso nao e uma
garantia automatica de conformidade regulatoria. A aprovacao depende do contexto
da instituicao, da politica de dados, da documentacao do modelo e da revisao de
governanca.
