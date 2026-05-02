# Implementar `force_numeric` no RiskBands

Você está trabalhando no projeto **RiskBands**.

## Contexto

As duas correções P1 anteriores já foram concluídas:

1. Fluxo categórico P1 corrigido.
2. `export_bundle` seguro contra path traversal e nomes inseguros de features.

Estado informado após a última etapa:

```text
tests/test_export_bundle_security.py        3 passed
tests/test_categorical_regressions.py       5 passed
suíte completa                              65 passed, 23 warnings
```

Nesta etapa, o foco é um problema P2 de API: o parâmetro público `force_numeric` existe no `Binner`, mas ainda não está efetivamente conectado à detecção de tipos usada pelo `fit`.

O objetivo é implementar `force_numeric` corretamente, com testes de regressão, sem misturar outras mudanças.

---

## Tarefa

Implemente corretamente o parâmetro público `force_numeric` no RiskBands.

A implementação deve garantir que colunas listadas em `force_numeric` sejam tratadas como numéricas durante `Binner.fit`, mesmo quando a heurística de detecção de tipos as classificaria como categóricas.

---

## Restrições importantes

- Não altere versão do pacote.
- Não altere `RELEASE.md`.
- Não altere workflows de CI/CD.
- Não publique nada em TestPyPI ou PyPI.
- Não mexa nas correções P1 já feitas para categóricas e `export_bundle`, exceto se for absolutamente necessário por compatibilidade, e nesse caso explique.
- Não refatore arquitetura ampla nesta etapa.
- Não mude a API pública além de ativar corretamente `force_numeric`.
- Não remova `force_categorical`.
- Não altere comportamento de colunas não listadas em `force_numeric`.
- Preserve compatibilidade com `fit`, `transform`, `fit_transform`, `describe_schema`, `binning_table` e `use_optuna`.

---

## Antes de alterar código

Inspecione:

- `riskbands/binning_engine.py`
- `riskbands/utils/dtypes.py`
- testes existentes relacionados a `Binner`, API pública e overrides de tipo
- chamadas atuais para `search_dtypes`
- fluxo com `use_optuna=True`

Confirme:

1. Como `search_dtypes` classifica colunas numéricas, categóricas e baixa cardinalidade.
2. Se `search_dtypes` já possui suporte parcial a `force_numeric`.
3. Onde `force_categorical` já é aplicado.
4. Onde `force_numeric` está sendo armazenado, mas não usado.

---

## Comportamento esperado

### 1. `force_numeric` deve forçar classificação numérica

Exemplo:

```python
binner = Binner(
    strategy="supervised",
    max_bins=4,
    min_event_rate_diff=0.0,
    force_numeric=["risk_bucket"],
)

binner.fit(df, y="target", column="risk_bucket")
```

Mesmo que `risk_bucket` tenha poucos valores distintos, ou seja originalmente detectável como categórica pela heurística, ela deve entrar em:

```python
binner.numeric_cols_
```

E não em:

```python
binner.cat_cols_
```

`describe_schema()` deve reportar essa coluna como `numeric`.

---

### 2. `force_numeric` e `force_categorical` não podem conflitar

Se a mesma coluna aparecer nas duas listas:

```python
Binner(
    force_numeric=["risk_bucket"],
    force_categorical=["risk_bucket"],
)
```

O `fit` deve lançar `ValueError` claro, mencionando `force_numeric`, `force_categorical` e o nome da coluna em conflito.

O erro deve ocorrer antes de treinar qualquer estratégia.

---

### 3. Colunas forçadas como numéricas devem ser validáveis como números

Se uma coluna listada em `force_numeric` tiver valores não conversíveis para número, o erro deve ser claro e antecipado.

Exemplo:

```python
df = pd.DataFrame(
    {
        "bad_numeric": ["A", "B", "C", "A"],
        "target": [0, 1, 0, 1],
    }
)

Binner(force_numeric=["bad_numeric"]).fit(df, y="target", column="bad_numeric")
```

Resultado esperado:

```text
ValueError claro indicando que a coluna forçada como numérica não pôde ser convertida para número.
```

Não deixe o erro escapar como exceção obscura de `OptimalBinning`, pandas ou NumPy.

---

### 4. Strings numéricas devem funcionar quando forçadas

Se uma coluna vier como `object`, mas os valores forem numericamente conversíveis, `force_numeric` deve permitir o fluxo numérico.

Exemplo:

```python
df = pd.DataFrame(
    {
        "risk_bucket": ["1", "2", "3", "1", "2", "3"],
        "target": [0, 0, 1, 0, 1, 1],
    }
)
```

Com:

```python
Binner(force_numeric=["risk_bucket"])
```

A coluna deve ser convertida de forma segura para numérica no fluxo interno de fit, classificada como numérica e transformável depois.

---

### 5. `force_categorical` deve continuar funcionando

Garanta que a correção de `force_numeric` não quebre `force_categorical`.

Uma coluna numérica forçada como categórica deve continuar entrando em:

```python
binner.cat_cols_
```

E não em:

```python
binner.numeric_cols_
```

---

### 6. `use_optuna=True` deve respeitar override por feature

Verifique o fluxo com `use_optuna=True`.

Se a feature foi forçada como numérica no `Binner` externo, o binner interno usado durante a otimização também deve tratar aquela feature como numérica.

Se a feature foi forçada como categórica no `Binner` externo, o binner interno usado durante a otimização também deve tratar aquela feature como categórica.

Não é necessário criar uma suíte pesada de Optuna. Use `n_trials` pequeno, por exemplo `2`, se o teste for criado.

---

## Sugestão de implementação

### Em `search_dtypes`

Se `search_dtypes` ainda não aceitar `force_numeric`, adicione argumento opcional:

```python
force_numeric: list[str] | None = None
```

A função deve:

1. Preservar comportamento atual quando `force_numeric=None` ou lista vazia.
2. Validar conflito entre `force_numeric` e `force_categorical`.
3. Validar se colunas forçadas existem no DataFrame, ignorando `target_col`.
4. Remover colunas de `force_numeric` da lista categórica, se a heurística as colocou ali.
5. Adicionar colunas de `force_numeric` à lista numérica, preservando a ordem original das colunas.
6. Garantir que `force_categorical` continue removendo a coluna da lista numérica e adicionando à categórica.

A ordem final deve respeitar a ordem das colunas no DataFrame.

---

### Em `Binner.fit`

Na chamada atual de `search_dtypes`, passe `force_numeric=self.force_numeric`.

Exemplo esperado:

```python
num_cols, cat_cols = search_dtypes(
    pd.concat([X_features, y.rename("target")], axis=1),
    target_col="target",
    limite_categorico=50,
    force_categorical=self.force_categorical,
    force_numeric=self.force_numeric,
    verbose=False,
)
```

Antes de treinar estratégias numéricas, converta as colunas forçadas como numéricas, se necessário:

```python
for col in forced_numeric_columns_present:
    X_features[col] = pd.to_numeric(X_features[col], errors="raise")
```

Se a conversão falhar, lance `ValueError` claro.

---

### Em `use_optuna=True`

Ao chamar `optimize_bins` para cada feature, preserve o override aplicável à feature atual.

Exemplo conceitual:

```python
feature_force_numeric = [col] if col in self.force_numeric else []
feature_force_categorical = [col] if col in self.force_categorical else []
```

E garanta que o binner interno criado por Optuna receba esse override.

Se for mais limpo, ajuste `optuna_optimizer.py` para aceitar e repassar esses overrides, mas mantenha a alteração pequena e bem testada.

---

## Testes obrigatórios

Crie um arquivo novo se não houver local melhor:

```text
tests/test_force_numeric.py
```

Ou adicione a arquivo existente de overrides/API, se já existir.

### Helper sugerido

```python
import numpy as np
import pandas as pd


def make_low_cardinality_numeric_frame(n=160, seed=123):
    rng = np.random.default_rng(seed)
    risk_bucket = rng.choice([1, 2, 3], size=n, p=[0.45, 0.35, 0.20])
    noise = rng.normal(size=n)
    proba = 0.05 + 0.12 * (risk_bucket == 2) + 0.28 * (risk_bucket == 3) + 0.03 * (noise > 0)
    proba = np.clip(proba, 0.01, 0.95)
    target = (rng.random(n) < proba).astype(int)
    return pd.DataFrame(
        {
            "risk_bucket": risk_bucket,
            "noise": noise,
            "target": target,
        },
        index=pd.Index(range(5000, 5000 + n), name="application_id"),
    )
```

---

### Teste 1 — `search_dtypes` respeita `force_numeric`

Nome sugerido:

```python
test_search_dtypes_respects_force_numeric_override
```

Comportamento:

- Criar DataFrame com coluna de baixa cardinalidade.
- Chamar `search_dtypes(..., force_numeric=["risk_bucket"])`.
- Verificar que `risk_bucket` aparece em `num_cols`.
- Verificar que `risk_bucket` não aparece em `cat_cols`.

---

### Teste 2 — `Binner.fit` classifica coluna forçada como numérica

Nome sugerido:

```python
test_binner_force_numeric_keeps_low_cardinality_feature_numeric
```

Comportamento:

```python
binner = Binner(
    strategy="supervised",
    max_bins=4,
    min_event_rate_diff=0.0,
    force_numeric=["risk_bucket"],
)

binner.fit(df, y="target", column="risk_bucket")
```

Asserts mínimos:

```python
assert "risk_bucket" in binner.numeric_cols_
assert "risk_bucket" not in binner.cat_cols_

schema = binner.describe_schema()
row = schema.loc[schema["col"] == "risk_bucket"].iloc[0]
assert row["tipo"] == "numeric"

transformed = binner.transform(df[["risk_bucket"]], return_type="dataframe")
assert transformed.index.equals(df.index)
assert list(transformed.columns) == ["risk_bucket"]
```

---

### Teste 3 — `force_categorical` continua tendo comportamento próprio

Nome sugerido:

```python
test_binner_force_categorical_still_overrides_numeric_dtype
```

Comportamento:

- Usar a mesma coluna `risk_bucket`, que é numérica.
- Instanciar `Binner(force_categorical=["risk_bucket"])`.
- Confirmar que ela entra em `cat_cols_` e não em `numeric_cols_`.
- Confirmar que `transform` funciona.

---

### Teste 4 — conflito entre `force_numeric` e `force_categorical`

Nome sugerido:

```python
test_binner_rejects_force_numeric_and_force_categorical_conflict
```

Comportamento:

```python
with pytest.raises(ValueError, match="force_numeric.*force_categorical.*risk_bucket|force_categorical.*force_numeric.*risk_bucket"):
    Binner(
        force_numeric=["risk_bucket"],
        force_categorical=["risk_bucket"],
    ).fit(df, y="target", column="risk_bucket")
```

---

### Teste 5 — string numérica forçada funciona

Nome sugerido:

```python
test_binner_force_numeric_accepts_numeric_strings
```

Comportamento:

- Transformar `risk_bucket` em string antes do fit:

```python
df["risk_bucket"] = df["risk_bucket"].astype(str)
```

- Usar `force_numeric=["risk_bucket"]`.
- Confirmar que fit e transform passam.
- Confirmar que `risk_bucket` está em `numeric_cols_`.

---

### Teste 6 — string não numérica forçada falha com erro claro

Nome sugerido:

```python
test_binner_force_numeric_rejects_non_numeric_strings_with_clear_error
```

Comportamento:

```python
df = pd.DataFrame(
    {
        "bad_numeric": ["A", "B", "C", "A", "B", "C", "A", "B"],
        "target": [0, 1, 0, 1, 0, 1, 0, 1],
    }
)

with pytest.raises(ValueError, match="force_numeric|numeric|bad_numeric"):
    Binner(force_numeric=["bad_numeric"]).fit(df, y="target", column="bad_numeric")
```

---

### Teste 7 — fluxo misto mantém ordem e schema

Nome sugerido:

```python
test_binner_force_numeric_mixed_frame_preserves_column_order_and_schema
```

Comportamento:

- DataFrame com `risk_bucket`, `noise` e `target`.
- Usar `columns=["risk_bucket", "noise"]`.
- Usar `force_numeric=["risk_bucket"]`.
- Confirmar que o `transform` devolve colunas na mesma ordem:

```python
assert list(transformed.columns) == ["risk_bucket", "noise"]
```

- Confirmar que ambas aparecem como numéricas em `describe_schema()`.

---

### Teste 8 — `use_optuna=True` respeita `force_numeric`

Nome sugerido:

```python
test_binner_force_numeric_is_respected_with_optuna
```

Comportamento:

- Usar dataset pequeno.
- Instanciar:

```python
binner = Binner(
    strategy="supervised",
    use_optuna=True,
    force_numeric=["risk_bucket"],
    strategy_kwargs={"n_trials": 2, "sampler_seed": 123},
)
```

- Fazer `fit` em `risk_bucket`.
- Confirmar que `risk_bucket` entra como numérica no binner externo.
- Se houver binner interno armazenado em `_per_feature_binners`, confirmar que ele também não classifica a variável como categórica, quando esse atributo estiver disponível.

Se o teste de Optuna ficar instável ou lento, mantenha-o pequeno e determinístico. Não marque como `skip` sem justificar.

---

## Comandos a executar

Rode primeiro os testes específicos:

```bash
python -m pytest -q tests/test_force_numeric.py --basetemp=.pytest_tmp/force_numeric
```

Depois rode as regressões P1 para garantir que nada quebrou:

```bash
python -m pytest -q tests/test_categorical_regressions.py tests/test_export_bundle_security.py --basetemp=.pytest_tmp/p1_after_force_numeric
```

Depois rode a suíte completa:

```bash
python -m pytest -q --basetemp=.pytest_tmp/full_after_force_numeric
```

Opcional, se disponível no ambiente:

```bash
python -m compileall -q riskbands
```

---

## Resultado esperado da resposta

Ao final, responda em português com:

1. Arquivos alterados.
2. Testes criados ou alterados.
3. Resumo técnico da implementação.
4. Como `force_numeric` passou a interagir com `search_dtypes`.
5. Como conflitos com `force_categorical` são tratados.
6. Como strings numéricas e strings não numéricas são tratadas.
7. Resultado dos comandos executados.
8. Confirmação de que os testes P1 categóricos e de export continuam passando.
9. Confirmação de que versão, `RELEASE.md`, workflows, PyPI e TestPyPI não foram alterados.
10. Próximo passo recomendado.

---

## Critério de aceite

A etapa só deve ser considerada concluída se:

```text
tests/test_force_numeric.py                  passed
tests/test_categorical_regressions.py        passed
tests/test_export_bundle_security.py         passed
suíte completa                               passed
```

E se o comportamento público abaixo estiver garantido:

```python
Binner(force_numeric=["risk_bucket"])
```

realmente força `risk_bucket` para o fluxo numérico.
