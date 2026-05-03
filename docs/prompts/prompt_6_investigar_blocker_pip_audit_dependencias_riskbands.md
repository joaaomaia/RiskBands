# Investigar blocker `pip-audit` e dependências transitivas do RiskBands

Você está trabalhando no projeto **RiskBands**.

## Contexto

A linha atual de trabalho já fechou os principais riscos funcionais antes da release:

- P1 categóricas corrigido.
- P1 `export_bundle` seguro corrigido.
- P2 `force_numeric` implementado e testado.
- CI foi reforçado com `ruff`, `pytest-cov`, `bandit`, `pip check` e `pip-audit`.
- A suíte local reportada está verde: `73 passed`, coverage total em torno de `79%`.
- Nada deve ser publicado em PyPI ou TestPyPI nesta etapa.

O blocker atual é de supply chain:

```text
riskbands -> optbinning 0.21.0 -> ortools 9.11.4210 -> protobuf 5.26.1
```

O `pip-audit` acusou vulnerabilidades em `protobuf 5.26.1`, aparentemente sem correção simples porque `ortools 9.11.4210` restringe `protobuf` para uma faixa incompatível com versões corrigidas.

## Objetivo desta etapa

Investigar tecnicamente o blocker `pip-audit` e gerar uma recomendação segura, reproduzível e documentada para o próximo passo.

Esta etapa é **investigação e decisão técnica**, não release.

## Regras importantes

- Não publique nada em PyPI ou TestPyPI.
- Não altere a versão do pacote.
- Não altere `RELEASE.md` nesta etapa.
- Não faça refatoração funcional.
- Não remova `pip-audit` apenas para “fazer o CI passar”.
- Não ignore CVEs sem justificar formalmente o risco.
- Se fizer qualquer alteração, ela deve ser mínima e focada apenas na governança do blocker.
- Se não houver solução técnica segura, diga explicitamente.

## Passo 0 — Conferir consistência do workspace

Antes de investigar dependências, confirme se os arquivos atuais no workspace refletem a etapa anterior:

- `pyproject.toml` deve conter no extra `dev`:
  - `pytest-cov`
  - `ruff`
  - `pip-audit`
  - `bandit`
- `pyproject.toml` deve conter configuração de coverage com `fail_under = 70`.
- `pyproject.toml` deve conter configuração de `ruff`.
- `.github/workflows/tests.yml` deve rodar `pip check`, `ruff`, `bandit`, `pytest --cov` e `pip-audit`.
- `.github/workflows/release-validation.yml` deve rodar `pip check`, `ruff`, `bandit`, suíte completa com coverage, `pip-audit`, build, `twine check`, smoke wheel e smoke sdist.

Se houver inconsistência entre `git diff`, arquivos locais e output anterior, reporte antes de prosseguir.

## Passo 1 — Reproduzir o blocker em ambiente limpo

Crie um ambiente limpo e rode:

```bash
python -m pip install --upgrade pip setuptools
python -m pip install -e .[dev]
python -m pip check
python -m pip_audit
python -m pip freeze
```

Gere arquivos de diagnóstico, se possível:

```bash
python -m pip_audit > pip_audit_output.txt || true
python -m pip freeze > pip_freeze_after_install.txt
python -m pip check > pip_check_output.txt || true
```

Se `pipdeptree` estiver disponível ou puder ser instalado no ambiente de diagnóstico, gere também:

```bash
python -m pip install pipdeptree
python -m pipdeptree > pipdeptree_output.txt
```

## Passo 2 — Confirmar a cadeia de dependência

Confirme, com evidências locais, a cadeia:

```text
riskbands -> optbinning -> ortools -> protobuf
```

Inclua:

- versão instalada de `optbinning`;
- versão instalada de `ortools`;
- versão instalada de `protobuf`;
- quais constraints impedem upgrade de `protobuf`;
- se o problema aparece em Python 3.11 e 3.12;
- se o problema muda com resolver limpo.

## Passo 3 — Testar alternativas de versionamento sem quebrar testes

Teste alternativas em ambientes isolados. Para cada alternativa, registre:

- comando de instalação;
- resultado do resolver;
- resultado de `pip check`;
- resultado de `pip-audit`;
- resultado dos testes críticos.

Testar, no mínimo:

### Alternativa A — Resolver atual

```bash
python -m pip install -e .[dev]
python -m pip check
python -m pip_audit
python -m pytest -q --basetemp .pytest_tmp/current --cov=riskbands --cov-report=term-missing
```

### Alternativa B — Forçar protobuf corrigido

Testar versões corrigidas indicadas pelo advisory, por exemplo:

```bash
python -m pip install "protobuf>=5.29.5"
python -m pip check
python -m pip_audit
python -m pytest -q --basetemp .pytest_tmp/protobuf_fixed
```

Se houver conflito com `ortools`, registrar o conflito exatamente.

### Alternativa C — Testar versões mais novas de OR-Tools

Verificar se alguma versão mais nova de `ortools` permite `protobuf` corrigido e ainda funciona com `optbinning`.

Exemplos, ajustando conforme disponibilidade:

```bash
python -m pip install "ortools>=9.13"
python -m pip check
python -m pip_audit
python -m pytest -q tests/test_categorical_regressions.py tests/test_force_numeric.py tests/test_binning_engine.py --basetemp .pytest_tmp/ortools_newer
```

Se `optbinning` impuser teto em `ortools`, registrar o conflito.

### Alternativa D — Testar versões de optbinning

Verificar se há versão de `optbinning` que resolva a cadeia transitiva.

Testar ao menos:

```bash
python -m pip install "optbinning==0.20.1"
python -m pip check
python -m pip_audit
```

```bash
python -m pip install "optbinning==0.21.0"
python -m pip check
python -m pip_audit
```

Se houver versão mais nova disponível, testar também.

### Alternativa E — Avaliar exposição real

Inspecione o código do RiskBands e responda:

- RiskBands processa arquivos `.proto`, mensagens protobuf ou JSON protobuf fornecidos pelo usuário?
- RiskBands chama diretamente `google.protobuf.json_format.ParseDict`?
- A exposição prática parece ser apenas transitiva via solver interno do OR-Tools?
- Existe algum caminho em que input externo não confiável possa alcançar parsing protobuf?

Atenção: exposição baixa não significa vulnerabilidade inexistente; significa apenas que a decisão pode ser de aceitação temporária de risco, se documentada.

## Passo 4 — Recomendar política para CI

Avalie qual política é mais adequada antes da release 2.0.3:

1. Manter `pip-audit` bloqueante em tudo, aceitando que CI fique vermelho até resolver.
2. Manter `pip-audit` bloqueante apenas em `release-validation.yml` e deixar o workflow regular `tests.yml` informativo enquanto o blocker upstream está aberto.
3. Usar `pip-audit --ignore-vuln` apenas para CVEs aceitos formalmente, com documentação clara, prazo de revisão e justificativa.
4. Aguardar upstream (`optbinning`/`ortools`) publicar combinação compatível com `protobuf` corrigido.
5. Tornar `optbinning` opcional ou criar fallback sem `optbinning`, se isso for viável sem quebrar a proposta do pacote.

Não aplique uma dessas políticas automaticamente sem explicar o trade-off.

## Passo 5 — Resultado esperado

Responda em português com:

1. Resumo executivo do blocker.
2. Cadeia exata de dependências e versões.
3. CVEs/advisories reportados pelo `pip-audit`.
4. Alternativas testadas e resultado de cada uma.
5. Avaliação de exposição real no código do RiskBands.
6. Recomendação objetiva para a política de CI.
7. Recomendação objetiva para a release 2.0.3.
8. Se sugerir exceção temporária, incluir:
   - CVE/advisory;
   - pacote afetado;
   - motivo da aceitação;
   - impacto potencial;
   - condição para remover a exceção;
   - prazo de revisão.
9. Confirmação de que nada foi publicado em PyPI/TestPyPI.
10. Próximo prompt sugerido para implementar a decisão.

## Critério de sucesso

Esta etapa será considerada concluída quando houver uma decisão clara entre:

- correção técnica por versionamento seguro;
- bloqueio de release até upstream corrigir;
- exceção temporária documentada;
- ajuste de CI separando desenvolvimento regular de release validation.

Não avance para publicação enquanto esta decisão não estiver fechada.
