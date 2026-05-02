# Corrigir segurança do `export_bundle` P1 no RiskBands

Você está trabalhando no projeto **RiskBands**.

## Contexto

Já foram criados testes de regressão P1 para dois grupos de risco:

1. Fluxo categórico.
2. Segurança do `export_bundle` contra path traversal e nomes inseguros de features.

A etapa anterior corrigiu somente o fluxo categórico. Os 5 testes categóricos passaram. As únicas falhas restantes esperadas são os 3 testes de segurança de `export_bundle`.

Agora o objetivo é corrigir **somente** o P1 de segurança de exportação do bundle.

## Escopo desta etapa

Corrigir a geração dos arquivos em `feature_tables` dentro de `export_bundle` / `export_binner_bundle`, impedindo que nomes de features sejam usados diretamente como caminhos de arquivo.

O problema conhecido está no padrão atual equivalente a:

```python
feature_path = feature_dir / f"{feature}.csv"
```

Esse uso direto do nome da feature permite:

- path traversal com `../` ou `..\\`;
- escrita fora do diretório do bundle;
- criação de subdiretórios dentro de `feature_tables`;
- nomes inválidos no Windows, como nomes com `:`;
- colisões após sanitização simples.

## Restrições obrigatórias

- Não publique nada em PyPI.
- Não publique nada em TestPyPI.
- Não altere versão.
- Não altere `RELEASE.md`.
- Não altere workflows de CI/CD.
- Não altere `pyproject.toml`, exceto se for absolutamente necessário para os testes, o que não deve ser o caso.
- Não altere os testes recém-criados para fazê-los passar artificialmente.
- Não refatore o `Binner` de forma ampla nesta etapa.
- Não mexa no fluxo categórico já corrigido, salvo se algum teste de regressão revelar uma interação direta e inevitável.
- Mantenha a API pública existente: `binner.export_bundle(path)` deve continuar funcionando.

## Arquivos prováveis

Inspecione antes de alterar:

- `riskbands/reporting.py`
- `riskbands/binning_engine.py`
- `tests/test_export_bundle_security.py`
- `tests/test_categorical_regressions.py`

A correção provavelmente deve ficar em `riskbands/reporting.py`, onde o bundle é efetivamente exportado.

## Testes que devem passar

Os testes já criados devem passar sem serem marcados como `xfail`, `skip` ou `flaky`:

- `test_export_bundle_does_not_write_feature_table_outside_bundle`
- `test_export_bundle_sanitizes_feature_names_with_path_separators`
- `test_export_bundle_handles_sanitized_feature_name_collisions`

Além disso, os testes categóricos já corrigidos devem continuar passando:

- `test_categorical_binning_transform_preserves_index_and_column_name`
- `test_categorical_binning_applies_learned_rare_mapping_on_transform`
- `test_binner_fit_transform_mixed_numeric_and_categorical_frame`
- `test_binner_fit_transform_matches_fit_then_transform_for_categorical_feature`
- `test_binner_categorical_transform_handles_unknown_and_missing_values`

## Comportamento esperado

### 1. Sanitização de nomes de artefatos

Implemente um helper interno para transformar nomes de features em nomes de arquivos seguros.

Nome sugerido:

```python
def _safe_artifact_name(name: object, *, fallback: str = "feature") -> str:
    ...
```

Requisitos do helper:

- aceitar qualquer nome de feature que possa ser convertido para string;
- remover ou substituir separadores de caminho `/` e `\\`;
- remover ou substituir `..` usado para path traversal;
- remover ou substituir caracteres problemáticos no Windows, como `:`, `*`, `?`, `"`, `<`, `>`, `|`;
- evitar nomes vazios;
- evitar nomes compostos apenas por pontos;
- limitar tamanho para algo seguro, por exemplo 80 ou 120 caracteres;
- retornar somente um nome de arquivo base, sem diretórios;
- não retornar path absoluto;
- preservar legibilidade quando possível.

Uma abordagem aceitável:

```python
import re
import unicodedata

_SAFE_ARTIFACT_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_artifact_name(name: object, *, fallback: str = "feature") -> str:
    text = str(name)
    text = unicodedata.normalize("NFKD", text)
    text = text.replace("/", "_").replace("\\\\", "_")
    text = text.replace("..", "_")
    text = _SAFE_ARTIFACT_RE.sub("_", text)
    text = text.strip("._- ")
    if not text:
        text = fallback
    return text[:100]
```

A implementação final pode ser diferente, mas deve atender aos requisitos e passar nos testes.

### 2. Tratamento de colisões

Implemente geração de nomes únicos para features diferentes que resultem no mesmo nome sanitizado.

Exemplo:

```python
features = ["feature/a", "feature:a", "feature a"]
```

Todos podem virar algo parecido com `feature_a`. Nesse caso, os arquivos devem ser únicos, por exemplo:

```text
feature_a.csv
feature_a_2.csv
feature_a_3.csv
```

Ou outra convenção determinística equivalente.

Requisitos:

- não sobrescrever arquivos;
- manter uma entrada no manifest para cada nome original de feature;
- garantir que os paths em `metadata["artifacts"]["feature_tables"]` sejam únicos;
- manter o resultado determinístico entre execuções com a mesma ordem de features.

### 3. Validação de path dentro do bundle

Antes de escrever cada CSV de feature, valide que o caminho final resolvido está dentro do diretório esperado.

Crie helper interno sugerido:

```python
def _ensure_path_inside(base: Path, candidate: Path) -> Path:
    base_resolved = base.resolve()
    candidate_resolved = candidate.resolve()
    if candidate_resolved != base_resolved and base_resolved not in candidate_resolved.parents:
        raise ValueError(f"Refusing to write outside target directory: {candidate}")
    return candidate
```

Use esse helper antes de gravar o arquivo.

Requisitos:

- validar contra `target_dir`, não apenas contra `feature_dir`;
- idealmente validar também contra `feature_dir` para garantir que as tabelas de features fiquem diretamente dentro de `feature_tables`;
- não deixar `Path.relative_to(target_dir)` quebrar por path fora do bundle; o path fora do bundle deve ser impossível antes disso.

### 4. Manifest/metadata

O `metadata.json` do bundle deve continuar tendo:

```python
metadata["artifacts"]["feature_tables"]
```

Mas agora os valores devem ser paths relativos seguros.

Exemplo esperado:

```json
{
  "artifacts": {
    "feature_tables": {
      "../../outside_bundle": "feature_tables/outside_bundle.csv",
      "feature/with/slash": "feature_tables/feature_with_slash.csv"
    }
  }
}
```

Requisitos:

- as chaves devem continuar sendo os nomes originais das features;
- os valores devem ser paths relativos ao diretório do bundle;
- os valores não podem ser absolutos;
- os valores não podem conter `..` em `Path(relative_path).parts`;
- o arquivo deve existir;
- o arquivo deve estar diretamente dentro de `feature_tables`;
- o nome do arquivo não deve conter `/` ou `\\`;
- se houver colisão, os paths devem ser únicos.

### 5. Compatibilidade

Garanta que exportações normais continuem funcionando para nomes simples:

```python
features = ["score", "idade", "renda"]
```

Não é obrigatório criar teste novo para isso se já houver cobertura, mas rode a suíte completa para confirmar que nada quebrou.

## Comandos a executar

Use `--basetemp` no workspace para evitar o problema de permissão observado no ambiente Windows.

Primeiro rode os testes específicos de export:

```bash
python -m pytest -q tests/test_export_bundle_security.py --basetemp=.pytest_tmp/export_fix
```

Depois rode novamente os testes categóricos para garantir que a correção anterior não foi afetada:

```bash
python -m pytest -q tests/test_categorical_regressions.py --basetemp=.pytest_tmp/categorical_after_export_fix
```

Depois rode a suíte completa:

```bash
python -m pytest -q --basetemp=.pytest_tmp/full_after_export_fix
```

## Resultado esperado

Ao final, responda em português com:

1. Arquivos alterados.
2. Helper(s) criado(s), com resumo breve do que fazem.
3. Como a sanitização lida com:
   - `../`;
   - `..\\`;
   - `/`;
   - `\\`;
   - `:`;
   - colisões.
4. Resultado dos comandos de teste.
5. Confirmação de que os 3 testes de `export_bundle` passaram.
6. Confirmação de que os 5 testes categóricos continuam passando.
7. Resultado da suíte completa.
8. Confirmação explícita de que não houve publicação em PyPI/TestPyPI.
9. Confirmação explícita de que versão, release notes e workflows não foram alterados.
10. Próximo passo recomendado.

## Critério de conclusão desta etapa

A etapa só está concluída quando:

```text
3 testes de export_bundle passam
5 testes categóricos passam
suíte completa passa
nenhum arquivo é escrito fora do bundle
metadata.json contém paths relativos seguros
não houve publicação em PyPI/TestPyPI
```

O próximo passo depois desta etapa será tratar `force_numeric` ou reforçar CI/coverage/security, mas não faça isso agora.
