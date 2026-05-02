# Testes de regressão P1 do RiskBands

> Objetivo: criar testes de regressão para os riscos P1 antes de qualquer correção de implementação.
>
> Status esperado desta etapa: os testes podem falhar na versão atual. Isso é desejado se eles expuserem os bugs.
>
> Regra principal: não publicar nada no PyPI/TestPyPI e não alterar código de produção.

---

## Prompt pronto para colar no Codex

Você está trabalhando no projeto RiskBands.

Contexto:
O RiskBands é uma biblioteca de binning para risco de crédito com foco em robustez temporal, comparação entre candidatos e racional auditável. A API pública principal expõe `Binner`, com suporte a variáveis numéricas, categóricas, diagnósticos, relatórios e exportação de artefatos. O objetivo agora NÃO é publicar no PyPI e NÃO é corrigir implementação ainda. O objetivo desta etapa é criar testes de regressão que exponham problemas P1 antes do patch.

Tarefa:
Crie testes automatizados de regressão para dois grupos de risco P1:

1. Robustez do fluxo categórico
2. Segurança do `export_bundle` contra path traversal e nomes inseguros de features

Importante:

- Não altere a implementação do pacote nesta etapa.
- Não corrija `CategoricalBinning`, `Binner`, `reporting.py`, `export_bundle` ou qualquer código de produção.
- Não altere versão, release notes, workflows ou configuração de publicação.
- Não publique nada em TestPyPI ou PyPI.
- Não marque os novos testes como `xfail`, `skip` ou `flaky`.
- Os testes devem ser escritos para falhar na versão atual caso o bug exista.
- Use dados sintéticos pequenos, determinísticos e rápidos.
- Use `pytest`.
- Prefira seguir o padrão dos testes já existentes no repositório.
- Se já houver arquivos de teste relacionados, adicione os testes neles. Caso contrário, crie arquivos novos.

Sugestão de arquivos:

- `tests/test_categorical_regressions.py`
- `tests/test_export_bundle_security.py`

Antes de escrever os testes:

1. Inspecione a estrutura do repositório.
2. Localize os testes existentes.
3. Localize a implementação de:
   - `riskbands.Binner`
   - `CategoricalBinning`
   - `export_bundle`
   - `export_binner_bundle`
4. Confirme os imports corretos conforme a estrutura real do projeto.

---

## PARTE 1 — Testes de regressão para categóricas

Crie testes cobrindo o fluxo categórico direto e o fluxo via `Binner`.

Objetivos mínimos:

- `fit` com coluna categórica simples não deve quebrar.
- `transform` após `fit` deve aceitar novas amostras.
- O índice original deve ser preservado no resultado do `transform`.
- O nome da coluna deve ser preservado.
- Categorias raras aprendidas no `fit` devem ser tratadas de forma determinística no `transform`.
- Categorias desconhecidas no `transform` não devem quebrar.
- Valores missing no `fit` e no `transform` não devem quebrar.
- Um DataFrame misto com feature numérica e feature categórica deve passar por `Binner.fit` e `Binner.transform`.
- `fit_transform` deve ser consistente com `fit` seguido de `transform`.

Use datasets sintéticos determinísticos. Exemplo de gerador, adaptando conforme necessário:

```python
import numpy as np
import pandas as pd


def make_categorical_credit_frame(n=240, seed=42):
    rng = np.random.default_rng(seed)

    grade = rng.choice(
        ["A", "B", "C", "D", "RARE_X", "RARE_Y"],
        size=n,
        p=[0.30, 0.25, 0.20, 0.18, 0.04, 0.03],
    )

    score = rng.normal(loc=0.0, scale=1.0, size=n)

    # Probabilidade correlacionada com categoria e score.
    grade_risk = {
        "A": 0.06,
        "B": 0.10,
        "C": 0.18,
        "D": 0.30,
        "RARE_X": 0.35,
        "RARE_Y": 0.40,
    }
    proba = np.array([grade_risk[g] for g in grade]) + 0.05 * (score > 0)
    proba = np.clip(proba, 0.01, 0.95)

    target = (rng.random(n) < proba).astype(int)

    df = pd.DataFrame(
        {
            "score": score,
            "grade": grade,
            "target": target,
        },
        index=pd.Index(range(1000, 1000 + n), name="custom_id"),
    )

    # Introduzir alguns missings de forma controlada.
    missing_idx = df.sample(8, random_state=seed).index
    df.loc[missing_idx, "grade"] = None

    return df
```

### Teste 1 — `CategoricalBinning` preserva índice e coluna no transform

Nome sugerido:

```python
test_categorical_binning_transform_preserves_index_and_column_name
```

Comportamento esperado:

- Instanciar `CategoricalBinning`.
- Fazer `fit` em uma única coluna categórica.
- Fazer `transform` em um DataFrame com índice não default.
- O resultado deve ser `pd.DataFrame`.
- O resultado deve ter exatamente a mesma quantidade de linhas.
- O resultado deve ter o mesmo índice do input.
- O resultado deve ter a mesma coluna original.
- O resultado não deve ser todo nulo.

Exemplo de assert:

```python
assert isinstance(transformed, pd.DataFrame)
assert transformed.index.equals(X_new.index)
assert list(transformed.columns) == ["grade"]
assert len(transformed) == len(X_new)
assert not transformed["grade"].isna().all()
```

### Teste 2 — rare categories aprendidas no fit são aplicadas no transform

Nome sugerido:

```python
test_categorical_binning_applies_learned_rare_mapping_on_transform
```

Comportamento esperado:

- Usar `rare_threshold` alto o suficiente para que `RARE_X` e `RARE_Y` sejam tratadas como raras.
- Após o `fit`, transformar um DataFrame contendo `RARE_X`, `RARE_Y`, uma categoria comum e uma categoria desconhecida.
- As categorias raras vistas no treino devem cair no mesmo tratamento/bin determinístico.
- A categoria desconhecida deve ser tratada sem exceção.
- Missing deve ser tratado sem exceção.

Exemplo de input:

```python
X_new = pd.DataFrame(
    {"grade": ["RARE_X", "RARE_Y", "A", "UNKNOWN_NEW_CATEGORY", None]},
    index=[501, 502, 503, 504, 505],
)
```

Asserts mínimos:

```python
transformed = cat_binner.transform(X_new)

assert transformed.index.equals(X_new.index)
assert list(transformed.columns) == ["grade"]
assert len(transformed) == len(X_new)
assert transformed["grade"].iloc[0] == transformed["grade"].iloc[1]
```

Observação:
Não exija um valor específico para o bin. Exija apenas comportamento determinístico e preservação da estrutura.

### Teste 3 — `Binner` funciona com DataFrame misto numérico + categórico

Nome sugerido:

```python
test_binner_fit_transform_mixed_numeric_and_categorical_frame
```

Comportamento esperado:

- Criar DataFrame com `score`, `grade` e `target`.
- Instanciar `Binner` com `strategy="supervised"`, `max_bins=4`, `min_event_rate_diff=0.0`.
- Usar `force_categorical=["grade"]` para garantir que `grade` entre no fluxo categórico.
- Fazer `fit(df, y="target", columns=["score", "grade"])`.
- Fazer `transform(df[["score", "grade"]])`.
- O resultado deve ter as colunas `score` e `grade`.
- O índice deve ser preservado.
- Não deve haver coluna extra.
- `binning_table()` deve conter as duas variáveis.

Asserts mínimos:

```python
assert transformed.index.equals(df.index)
assert list(transformed.columns) == ["score", "grade"]

table = binner.binning_table()
assert set(table["variable"]) == {"score", "grade"}
```

### Teste 4 — `fit_transform` é consistente com `fit` + `transform`

Nome sugerido:

```python
test_binner_fit_transform_matches_fit_then_transform_for_categorical_feature
```

Comportamento esperado:

- Criar dois `Binner` com os mesmos parâmetros.
- No primeiro, rodar `fit_transform`.
- No segundo, rodar `fit` e depois `transform`.
- Comparar os resultados para a feature categórica.
- Ambos devem preservar índice e nome da coluna.

Exemplo:

```python
b1 = Binner(
    strategy="supervised",
    max_bins=4,
    min_event_rate_diff=0.0,
    force_categorical=["grade"],
)

out_fit_transform = b1.fit_transform(
    df,
    y="target",
    column="grade",
    return_type="dataframe",
)

b2 = Binner(
    strategy="supervised",
    max_bins=4,
    min_event_rate_diff=0.0,
    force_categorical=["grade"],
)

b2.fit(df, y="target", column="grade")
out_separate = b2.transform(df[["grade"]], return_type="dataframe")

pd.testing.assert_frame_equal(out_fit_transform, out_separate)
```

### Teste 5 — categorias desconhecidas e missing no transform via `Binner`

Nome sugerido:

```python
test_binner_categorical_transform_handles_unknown_and_missing_values
```

Comportamento esperado:

- Treinar com categorias conhecidas.
- Transformar novo DataFrame com:
  - categoria conhecida;
  - categoria rara vista no treino;
  - categoria desconhecida;
  - missing.
- Não deve lançar exceção.
- Deve preservar índice.
- Deve preservar coluna.
- O output deve ter mesmo número de linhas.

---

## PARTE 2 — Testes de segurança para `export_bundle`

Crie testes para impedir path traversal e nomes de arquivos inseguros na exportação do bundle.

Contexto técnico:
O export atual gera arquivos em `feature_tables` usando o nome da feature como parte do caminho do CSV. Isso precisa ser protegido por testes antes da correção.

Objetivos mínimos:

- Uma feature com nome malicioso não pode escrever arquivo fora do diretório alvo do bundle.
- O manifest/metadata não pode conter paths absolutos.
- O manifest/metadata não pode conter paths com `..`.
- Os paths de `feature_tables` devem resolver para dentro do diretório do bundle.
- Nomes com separadores `/` ou `\` não devem gerar subdiretórios inesperados dentro de `feature_tables`.
- Colisões após sanitização futura devem ser cobertas por teste.

Use `tmp_path`.

Crie helper de teste para validar path seguro:

```python
from pathlib import Path


def assert_path_inside(base: Path, candidate: Path):
    base_resolved = base.resolve()
    candidate_resolved = candidate.resolve()
    assert candidate_resolved == base_resolved or base_resolved in candidate_resolved.parents
```

E helper para ler metadata:

```python
import json


def read_bundle_metadata(bundle_dir):
    return json.loads((bundle_dir / "metadata.json").read_text(encoding="utf-8"))
```

### Teste 6 — feature maliciosa não escreve fora do bundle

Nome sugerido:

```python
test_export_bundle_does_not_write_feature_table_outside_bundle
```

Use uma coluna com nome malicioso, por exemplo:

```python
malicious_feature = "../../outside_bundle"
```

Monte um DataFrame sintético:

```python
df = pd.DataFrame(
    {
        malicious_feature: rng.normal(size=n),
        "target": target,
    }
)
```

Fluxo:

```python
bundle_dir = tmp_path / "bundle"
outside_file = tmp_path / "outside_bundle.csv"

binner.fit(df, y="target", column=malicious_feature)
binner.export_bundle(bundle_dir)
```

Asserts esperados:

```python
assert bundle_dir.exists()
assert (bundle_dir / "metadata.json").exists()
assert not outside_file.exists()
```

Depois, valide todos os paths em `metadata["artifacts"]["feature_tables"]`:

```python
metadata = read_bundle_metadata(bundle_dir)
feature_tables = metadata["artifacts"]["feature_tables"]

assert feature_tables

for original_feature, relative_path in feature_tables.items():
    assert not Path(relative_path).is_absolute()
    assert ".." not in Path(relative_path).parts
    assert "/" not in Path(relative_path).name
    assert "\\" not in Path(relative_path).name

    resolved_path = bundle_dir / relative_path
    assert_path_inside(bundle_dir, resolved_path)
    assert resolved_path.exists()
```

Observação:
Este teste provavelmente deve falhar na versão atual se o path traversal estiver presente. Não corrija ainda.

### Teste 7 — nomes com separadores não criam subdiretórios em `feature_tables`

Nome sugerido:

```python
test_export_bundle_sanitizes_feature_names_with_path_separators
```

Use nomes como:

```python
features = ["feature/with/slash", "feature\\with\\backslash"]
```

Fluxo:

- Criar DataFrame com essas duas features numéricas e `target`.
- Treinar `Binner`.
- Exportar bundle.
- Verificar `metadata["artifacts"]["feature_tables"]`.

Asserts esperados:

- Cada path relativo deve começar por `feature_tables/` ou equivalente em `Path.parts`.
- O arquivo final de cada feature deve estar diretamente dentro de `feature_tables`, sem subdiretórios adicionais.
- O nome do arquivo não deve conter `/`, `\` ou `..`.
- Todos os paths devem resolver dentro do bundle.

Exemplo:

```python
feature_tables_dir = bundle_dir / "feature_tables"

for relative_path in feature_tables.values():
    path = Path(relative_path)

    assert not path.is_absolute()
    assert ".." not in path.parts

    resolved_path = bundle_dir / path
    assert_path_inside(bundle_dir, resolved_path)

    assert resolved_path.parent == feature_tables_dir
    assert resolved_path.exists()

    assert "/" not in resolved_path.name
    assert "\\" not in resolved_path.name
```

### Teste 8 — colisões de nomes sanitizados não sobrescrevem arquivos

Nome sugerido:

```python
test_export_bundle_handles_sanitized_feature_name_collisions
```

Use features que provavelmente colidiriam após sanitização simples:

```python
features = ["feature/a", "feature:a", "feature a"]
```

Comportamento esperado:

- Exportar todas as features.
- O manifest deve conter uma entrada para cada feature original.
- Os paths dos arquivos devem ser únicos.
- Todos os arquivos devem existir.
- Nenhum arquivo deve ser sobrescrito.

Asserts:

```python
metadata = read_bundle_metadata(bundle_dir)
feature_tables = metadata["artifacts"]["feature_tables"]

assert set(feature_tables) == set(features)

paths = list(feature_tables.values())
assert len(paths) == len(set(paths))

for relative_path in paths:
    resolved_path = bundle_dir / relative_path
    assert_path_inside(bundle_dir, resolved_path)
    assert resolved_path.exists()
```

---

## Comandos a rodar

Depois de criar os testes, rode no mínimo:

```bash
python -m pytest -q tests/test_categorical_regressions.py tests/test_export_bundle_security.py
```

Se os nomes dos arquivos forem diferentes, ajuste o comando.

Depois rode a suíte completa:

```bash
python -m pytest -q
```

---

## Resultado esperado da resposta do Codex

Ao final, responda em português com:

1. Arquivos de teste criados ou alterados.
2. Lista dos novos testes adicionados.
3. Comando(s) executado(s).
4. Resultado dos testes.
5. Quais testes falharam na versão atual e por quê.
6. Confirmação explícita de que nenhuma implementação foi alterada.
7. Confirmação explícita de que nada foi publicado em PyPI/TestPyPI.
8. Próximo passo recomendado, sem aplicar ainda.

Lembre-se:
Esta etapa é apenas para criar os testes de regressão P1. A correção dos bugs será feita em uma etapa posterior.
