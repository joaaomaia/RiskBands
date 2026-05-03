# Implementar correção de supply chain do protobuf, OR-Tools e OptBinning no RiskBands

Você está trabalhando no projeto **RiskBands**.

## Contexto

O projeto está em fase de hardening pré-release para uma futura versão `2.0.3`.

Já foram corrigidos e validados pontos P1/P2 importantes:

- fluxo categórico;
- segurança do `export_bundle`;
- `force_numeric`;
- gates de qualidade com `ruff`, `pytest-cov`, `bandit`, `pip check` e `pip-audit`.

A publicação em PyPI/TestPyPI continua bloqueada.

Agora há um blocker de supply chain detectado por `pip-audit`.

Cadeia vulnerável reproduzida:

```text
riskbands 2.0.2
  -> optbinning 0.21.0
    -> ortools 9.11.4210
      -> protobuf 5.26.1
```

`pip-audit` reporta vulnerabilidades em `protobuf 5.26.1`:

```text
protobuf 5.26.1  CVE-2025-4565  fix: 4.25.8, 5.29.5, 6.31.1
protobuf 5.26.1  CVE-2026-0994  fix: 5.29.6, 6.33.5
```

A investigação anterior encontrou uma combinação candidata segura:

```text
optbinning 0.21.0
ortools 9.10.4067
protobuf 5.29.6
```

Resultado reportado na investigação:

- `pip check`: passou;
- `pip-audit`: passou;
- testes críticos: `14 passed`;
- suíte completa: `73 passed`;
- coverage total: aproximadamente `79.17%`;
- resolver simulado para Python 3.12 também escolheu a combinação segura.

## Objetivo desta etapa

Implementar a correção de supply chain no projeto, tornando a combinação segura parte explícita das dependências do pacote.

O objetivo é evitar que o resolver instale `ortools 9.11.4210` com `protobuf 5.26.1`.

## Escopo permitido

Você pode alterar:

- `pyproject.toml`;
- arquivos de documentação técnica mínima, se necessário, por exemplo:
  - notas internas de dependência;
  - comentário em docs de desenvolvimento;
  - arquivo de registro de decisão, se já existir no projeto.

Você pode criar, se fizer sentido:

- um pequeno documento em `docs/` ou `docs/project_state/` explicando a decisão de dependências;
- um teste ou script leve de sanity check de dependências, desde que não complique a API pública.

## Escopo proibido

Não altere nesta etapa:

- versão do pacote;
- `RELEASE.md`;
- release notes finais;
- workflows de publicação;
- código funcional de binning;
- código categórico;
- `export_bundle`;
- `force_numeric`;
- API pública;
- documentação de marketing;
- README principal, salvo se houver uma razão técnica muito clara.

Não publique nada em PyPI ou TestPyPI.

Não use `pip-audit --ignore-vuln`.

Não remova `pip-audit` dos workflows.

Não transforme `pip-audit` em warning informativo.

## Alteração esperada no `pyproject.toml`

Atualize as dependências runtime para impedir a combinação vulnerável.

Candidate preferencial:

```toml
dependencies = [
  "pandas>=2.0",
  "numpy>=1.24",
  "scikit-learn>=1.4",
  "scipy>=1.11",
  "optbinning>=0.21.0,<0.22",
  "ortools>=9.10.4067,<9.11",
  "protobuf>=5.29.6,<6",
  "optuna>=3.5.0",
  "category_encoders>=2.6",
  "matplotlib>=3.8",
  "seaborn>=0.13",
  "tqdm>=4.66"
]
```

Observações:

1. A ideia é manter `optbinning` em `0.21.x`, pois foi a versão validada.
2. A ideia é bloquear `ortools 9.11.4210`, pois ele prende `protobuf` em `<5.27`.
3. A ideia é exigir `protobuf>=5.29.6`, pois é a primeira faixa 5.x que cobre os dois CVEs reportados.
4. A ideia é manter `<6` para evitar salto major não validado nesta release.
5. Se a combinação acima não resolver em ambiente limpo, pare e explique o conflito. Não force uma solução não testada.

## Validações obrigatórias

Rode em ambiente limpo sempre que possível.

### 1. Reinstalação limpa

Crie uma venv limpa e instale o projeto com extra dev:

```bash
python -m venv .venv-supply-chain
. .venv-supply-chain/Scripts/activate  # Windows PowerShell/Git Bash: adapte se necessário
python -m pip install --upgrade pip setuptools
python -m pip install -e .[dev]
```

Em Linux/macOS:

```bash
python -m venv .venv-supply-chain
. .venv-supply-chain/bin/activate
python -m pip install --upgrade pip setuptools
python -m pip install -e .[dev]
```

### 2. Confirmar versões instaladas

Rode:

```bash
python - <<'PY'
import importlib.metadata as md

for package in ["riskbands", "optbinning", "ortools", "protobuf"]:
    try:
        print(f"{package}=={md.version(package)}")
    except md.PackageNotFoundError:
        print(f"{package}: NOT INSTALLED")
PY
```

Resultado esperado:

```text
optbinning==0.21.0
ortools==9.10.4067
protobuf==5.29.6
```

Ou versões equivalentes dentro dos ranges seguros:

```text
optbinning>=0.21.0,<0.22
ortools>=9.10.4067,<9.11
protobuf>=5.29.6,<6
```

### 3. Resolver tree

Instale e rode `pipdeptree`, se necessário:

```bash
python -m pip install pipdeptree
python -m pipdeptree > pipdeptree_after_supply_chain_fix.txt
```

Verifique explicitamente que não existe:

```text
ortools==9.11.4210
protobuf==5.26.1
```

### 4. Consistência de dependências

```bash
python -m pip check
```

Esperado:

```text
No broken requirements found.
```

### 5. Auditoria de dependências

```bash
python -m pip_audit
```

Esperado:

```text
No known vulnerabilities found
```

ou resultado equivalente sem CVE em `protobuf`.

### 6. Lint

```bash
python -m ruff check riskbands tests
```

### 7. Bandit

```bash
python -m bandit -q -r riskbands
```

### 8. Testes com coverage

```bash
python -m pytest -q --basetemp .pytest_tmp/supply_chain_fix --cov=riskbands --cov-report=term-missing
```

Esperado:

```text
73 passed
coverage >= 70%
```

Ou número maior de testes, caso a suíte tenha crescido.

### 9. Build e metadata

```bash
python -m build
python -m twine check dist/*
```

### 10. Smoke wheel com extra `viz`

Instale o wheel em ambiente limpo e rode o smoke existente:

```bash
python -m venv .venv-smoke-supply-chain
. .venv-smoke-supply-chain/Scripts/activate  # adapte em Linux/macOS
python -m pip install --upgrade pip setuptools
python -m pip install "dist/<NOME_DO_WHEEL>[viz]"
python scripts/smoke_test_installed_package.py --expected-version 2.0.2 --check-viz
python -m pip check
python -m pip_audit
```

A versão esperada continua `2.0.2` nesta etapa, porque ainda não estamos preparando a release `2.0.3`.

## Validação Python 3.12

Se houver Python 3.12 disponível localmente, repita a instalação limpa e os checks críticos em Python 3.12.

Se não houver Python 3.12 local, registre isso e faça uma simulação de resolver para Python 3.12 quando possível.

Sugestão, se aplicável:

```bash
python -m pip download \
  --only-binary=:all: \
  --python-version 3.12 \
  --implementation cp \
  --abi cp312 \
  --platform win_amd64 \
  "ortools>=9.10.4067,<9.11" \
  "protobuf>=5.29.6,<6" \
  "optbinning>=0.21.0,<0.22" \
  -d .pytest_tmp/resolver_cp312_win
```

Se o comando não for adequado ao ambiente, use alternativa equivalente e explique.

## Registro técnico da decisão

Se criar documentação, registre de forma objetiva:

- qual era a cadeia vulnerável;
- quais CVEs foram reportados;
- por que não foi usado `--ignore-vuln`;
- qual combinação foi escolhida;
- quais checks passaram;
- que PyPI/TestPyPI continuam bloqueados até a preparação final da release.

Não faça documentação longa nesta etapa.

## Resultado esperado da sua resposta

Ao final, responda em português com:

1. Arquivos alterados.
2. Dependências antes/depois.
3. Versões instaladas em ambiente limpo.
4. Resultado de:
   - `pip check`;
   - `pip-audit`;
   - `ruff`;
   - `bandit`;
   - `pytest` com coverage;
   - `build`;
   - `twine check`;
   - smoke wheel, se executado.
5. Se Python 3.12 foi validado ou simulado.
6. Confirmação explícita de que:
   - versão não foi alterada;
   - `RELEASE.md` não foi alterado;
   - workflows de publicação não foram alterados;
   - nada foi publicado em PyPI/TestPyPI.
7. Próximo passo recomendado.

## Critério de aceite

A etapa só deve ser considerada concluída se:

- `pyproject.toml` impede `ortools 9.11.4210`;
- `pyproject.toml` impede `protobuf 5.26.1`;
- `pip check` passa em ambiente limpo;
- `pip-audit` passa em ambiente limpo;
- a suíte passa com coverage acima do limite configurado;
- build e `twine check` passam;
- não houve publicação.
