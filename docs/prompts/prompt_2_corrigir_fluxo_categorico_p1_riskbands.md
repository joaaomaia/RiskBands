# Corrigir fluxo categórico P1 do RiskBands

Você está trabalhando no projeto **RiskBands**.

## Contexto

Na etapa anterior, foram criados testes de regressão P1 para expor falhas reais antes de qualquer patch.  
Os testes foram adicionados em:

- `tests/test_categorical_regressions.py`
- `tests/test_export_bundle_security.py`

Resultado reportado após criação dos testes:

```text
Bateria específica: 8 failed
Suíte completa: 8 failed, 57 passed, 24 warnings
```

Falhas categóricas expostas:

```text
Os 5 testes categóricos falham porque CategoricalBinning.fit quebra no fluxo atual:
- OptimalBinning rejeita o argumento prebin_cat;
- o fallback com category_encoders.OrdinalEncoder falha com:
  AttributeError: 'OrdinalEncoder' object has no attribute '_get_tags'
```

Falhas de export expostas:

```text
Os 3 testes de export_bundle ainda falham porque nomes de features inseguros
permitem path traversal, criação de subdiretórios e nomes inválidos no Windows.
```

## Objetivo desta etapa

Corrigir **somente o fluxo categórico P1**.

A correção de `export_bundle` será feita em outro prompt.  
Não misture as duas correções nesta etapa.

## Escopo permitido

Você pode alterar código de produção apenas onde for necessário para corrigir o fluxo categórico:

- `riskbands/strategies/categorical.py`
- `riskbands/binning_engine.py`, somente se for indispensável para preservar integração com `Binner` ou `get_bin_mapping`

Evite alterar outros módulos.

## Fora de escopo

Não faça nesta etapa:

- Não corrija `export_bundle`
- Não altere `reporting.py` por causa dos testes de export
- Não altere os testes recém-criados, exceto se houver erro evidente de import/caminho
- Não marque testes como `xfail`, `skip` ou `flaky`
- Não altere versão do pacote
- Não altere `RELEASE.md`
- Não altere workflows
- Não altere `pyproject.toml`, salvo se for absolutamente inevitável — e nesse caso justifique
- Não publique nada em TestPyPI
- Não publique nada em PyPI

## Testes que devem passar ao final desta etapa

Os cinco testes categóricos devem passar:

```text
test_categorical_binning_transform_preserves_index_and_column_name
test_categorical_binning_applies_learned_rare_mapping_on_transform
test_binner_fit_transform_mixed_numeric_and_categorical_frame
test_binner_fit_transform_matches_fit_then_transform_for_categorical_feature
test_binner_categorical_transform_handles_unknown_and_missing_values
```

Os três testes de export podem continuar falhando nesta etapa, pois serão corrigidos depois:

```text
test_export_bundle_does_not_write_feature_table_outside_bundle
test_export_bundle_sanitizes_feature_names_with_path_separators
test_export_bundle_handles_sanitized_feature_name_collisions
```

## Requisitos funcionais da correção categórica

A implementação corrigida deve garantir:

1. `CategoricalBinning.fit` funciona com uma coluna categórica simples.
2. `CategoricalBinning.transform` funciona após `fit`.
3. `transform` preserva o índice original do input.
4. `transform` preserva o nome original da coluna.
5. `transform` retorna sempre `pd.DataFrame`.
6. Categorias raras aprendidas no `fit` são tratadas de forma determinística no `transform`.
7. Duas categorias raras vistas no treino, como `RARE_X` e `RARE_Y`, devem cair no mesmo tratamento/bin.
8. Categoria desconhecida no `transform` não deve lançar exceção.
9. Valor missing no `fit` não deve lançar exceção.
10. Valor missing no `transform` não deve lançar exceção.
11. `Binner.fit` e `Binner.transform` devem funcionar com DataFrame misto contendo variável numérica e categórica.
12. `Binner.fit_transform` deve ser consistente com `fit` seguido de `transform`.
13. A correção não pode quebrar variáveis numéricas.

## Diagnóstico técnico esperado

Antes de aplicar o patch, inspecione:

- `riskbands/strategies/categorical.py`
- `riskbands/binning_engine.py`
- testes existentes de API pública
- testes novos em `tests/test_categorical_regressions.py`

Confirme onde o fluxo quebra:

1. `OptimalBinning(dtype="categorical")` recebe argumento não suportado, como `prebin_cat`.
2. O fallback atual depende de `category_encoders.OrdinalEncoder`.
3. A combinação atual de `category_encoders` e `scikit-learn` pode falhar com `_get_tags`.
4. O rare-merge é aplicado no `fit`, mas o estado aprendido não é reaplicado de forma explícita e confiável no `transform`.
5. O caminho `transform` com `OptimalBinning` não preserva índice.
6. O fluxo precisa ser robusto mesmo quando o backend categorical do `OptimalBinning` falhar.

## Diretriz de design

A correção deve priorizar robustez e previsibilidade.

Não dependa exclusivamente de `category_encoders.OrdinalEncoder` como fallback.  
Implemente um fallback interno e determinístico para categóricas, caso o `OptimalBinning` categórico falhe ou não seja compatível com a versão instalada.

O fallback interno deve ser simples, auditável e suficiente para produção controlada, mesmo que o `OptimalBinning` categórico não esteja disponível.

## Requisitos de estado interno em `CategoricalBinning`

Ao final do `fit`, o objeto deve manter atributos suficientes para reproduzir o tratamento no `transform`.

Sugestão de atributos, ajuste conforme o padrão do projeto:

```python
self.feature_name_
self.rare_categories_
self.known_categories_
self.category_mapping_
self.default_bin_
self.missing_token_
self.rare_token_
self.unknown_token_
self._encoder
self.bin_summary_
```

Tokens sugeridos:

```python
_MISSING_
_RARE_
_UNKNOWN_
```

## Normalização de categorias

Crie uma função interna para preparar a coluna categórica, por exemplo:

```python
def _prepare_series(self, X, *, fit: bool) -> pd.Series:
    ...
```

Ela deve:

- aceitar `pd.DataFrame` com exatamente uma coluna;
- preservar o índice;
- converter valores categóricos para representação estável;
- tratar missing com token explícito, como `_MISSING_`;
- no `fit`, identificar categorias raras com base em `rare_threshold`;
- no `fit`, mapear categorias raras para `_RARE_`;
- no `transform`, reaplicar exatamente o mapeamento aprendido;
- no `transform`, mapear categorias desconhecidas para tratamento determinístico;
- não modificar o input original.

Exemplo de comportamento esperado:

```text
fit vê RARE_X e RARE_Y como raras
transform(["RARE_X", "RARE_Y"]) deve gerar o mesmo bin/código para ambas
transform(["UNKNOWN_NEW_CATEGORY"]) não deve quebrar
transform([None]) não deve quebrar
```

Não exija que a categoria desconhecida tenha um bin novo.  
Ela pode cair em um bin padrão, desde que o comportamento seja determinístico e documentável.

## Uso de OptimalBinning categorical

Se você continuar tentando usar `OptimalBinning(dtype="categorical")`, faça isso de modo compatível:

- não passe argumentos não suportados pela versão instalada;
- remova `prebin_cat=True` se ele não existir na assinatura da versão usada;
- preferencialmente use `inspect.signature` ou configuração explícita compatível;
- capture exceções de forma controlada;
- registre a razão do fallback em atributo interno, por exemplo `self._fallback_reason_`;
- antes de aceitar o backend `OptimalBinning`, valide que ele consegue transformar:
  - dados de treino;
  - categorias raras já vistas;
  - missing;
  - uma categoria desconhecida normalizada.

Se o backend categorical não for confiável para unknown/missing, use fallback interno.

## Fallback interno recomendado

Implemente um fallback manual, sem depender de `category_encoders.OrdinalEncoder`.

Uma abordagem aceitável:

1. Usar a série normalizada após rare/missing treatment.
2. Calcular por categoria:
   - `count`
   - `event`
   - `non_event`
   - `event_rate`
3. Ordenar categorias por `event_rate`, depois por nome da categoria para desempate determinístico.
4. Agrupar categorias em no máximo `max_bins` bins, se necessário.
5. Criar um mapeamento `categoria_normalizada -> bin`.
6. Guardar esse mapeamento em `self.category_mapping_`.
7. Definir um `self.default_bin_` para categorias desconhecidas.
8. Retornar sempre os bins pelo mapping aprendido.

O fallback deve gerar `bin_summary_` com pelo menos estas colunas:

```text
variable
bin
count
event
non_event
event_rate
```

Essas colunas são necessárias porque o `Binner` passa `strat.bin_summary_` para `refine_bins`.

## Integração com `Binner`

Garanta que o fluxo abaixo funcione:

```python
binner = Binner(
    strategy="supervised",
    max_bins=4,
    min_event_rate_diff=0.0,
    force_categorical=["grade"],
)

binner.fit(df, y="target", columns=["score", "grade"])
transformed = binner.transform(df[["score", "grade"]])
```

O resultado deve:

- preservar índice;
- ter exatamente as colunas `["score", "grade"]`;
- incluir `score` e `grade` em `binner.binning_table()`;
- não alterar o comportamento numérico.

## Compatibilidade com `get_bin_mapping`

Verifique `Binner.get_bin_mapping`.

Hoje ele pode assumir tipos específicos de encoder.  
Se a correção introduzir um fallback manual, ajuste `get_bin_mapping` para retornar um DataFrame coerente também nesse caso.

Formato esperado:

```text
categoria
bin
```

Não precisa criar teste novo para isso nesta etapa, mas a API não deve quebrar se chamada com uma categórica ajustada pelo fallback manual.

## Critérios de aceite

Ao final desta etapa:

1. Os 5 testes de `tests/test_categorical_regressions.py` passam.
2. Os 3 testes de export continuam sem correção, salvo se passarem incidentalmente sem alteração de `export_bundle`.
3. A suíte completa deve ter, no máximo, as falhas conhecidas de export.
4. Nenhum teste categórico deve ser marcado como skip/xfail.
5. Nenhum código de publicação deve ser alterado.
6. Nenhuma versão deve ser alterada.
7. Nada deve ser publicado em TestPyPI/PyPI.

## Comandos a executar

Use `--basetemp` dentro do workspace, pois o ambiente anterior teve `PermissionError` no temp padrão do Windows.

Primeiro, rode apenas os testes categóricos:

```powershell
python -m pytest -q tests/test_categorical_regressions.py --basetemp=.pytest_tmp\categorical_fix
```

Depois rode os testes de export para confirmar que não foram corrigidos nesta etapa por engano:

```powershell
python -m pytest -q tests/test_export_bundle_security.py --basetemp=.pytest_tmp\export_still_pending
```

Resultado esperado neste segundo comando:

```text
3 failed
```

Depois rode a suíte completa:

```powershell
python -m pytest -q --basetemp=.pytest_tmp\full_after_categorical_fix
```

Resultado esperado:

```text
Todos os testes antigos e os 5 categóricos passam.
Podem restar somente as 3 falhas de export_bundle.
```

Se a suíte completa tiver falhas além das 3 de export, investigue e corrija se forem consequência do patch categórico.

## Resposta esperada

Ao final, responda em português com:

1. Arquivos alterados.
2. Resumo técnico do que foi corrigido.
3. Como o rare-merge passou a ser persistido e reaplicado.
4. Como unknown e missing são tratados no `transform`.
5. Se `OptimalBinning` categórico ainda é usado ou se o fallback manual foi acionado.
6. Resultado dos comandos executados.
7. Confirmação de que os 5 testes categóricos passaram.
8. Confirmação de que `export_bundle` não foi corrigido nesta etapa.
9. Confirmação de que versão/release/workflows/PyPI/TestPyPI não foram alterados.
10. Próximo passo recomendado: corrigir segurança do `export_bundle`.
