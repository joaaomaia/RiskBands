# Limpeza segura da worktree, `.gitignore` e commits segmentados — RiskBands

Você está trabalhando no repositório local do projeto **RiskBands**.

## Contexto

O projeto passou por uma sequência de hardening antes da futura release `2.0.3`, ainda sem publicar nada em PyPI/TestPyPI.

Mudanças recentes esperadas no workspace:

1. Testes de regressão P1 para categóricas e `export_bundle`.
2. Correção do fluxo categórico.
3. Correção de segurança do `export_bundle` contra path traversal e nomes inseguros de features.
4. Implementação de `force_numeric`.
5. Reforço de quality gates em `pyproject.toml`, `tests.yml` e `release-validation.yml`.
6. Correção de supply chain para evitar a cadeia vulnerável:
   - antes: `optbinning 0.21.0 -> ortools 9.11.4210 -> protobuf 5.26.1`
   - depois esperado:
     - `optbinning>=0.21.0,<0.22`
     - `ortools>=9.10.4067,<9.11`
     - `protobuf>=5.29.6,<6`
7. Criação de documentação técnica curta sobre dependências em `docs/supply_chain_dependencies.md`.

Problema atual:

A worktree local tem **mais de 10 mil arquivos untracked** em relação ao GitHub. Precisamos organizar o repositório, melhorar o `.gitignore` e fazer commits em partes, **somente com arquivos relevantes e seguros**.

## Objetivo desta etapa

Fazer uma limpeza e organização profissional da worktree, com foco em:

- evitar vazamento de dados sensíveis;
- evitar commit de artefatos temporários, caches, builds, logs, datasets e outputs locais;
- melhorar `.gitignore` com segurança;
- separar as mudanças relevantes em commits pequenos e revisáveis;
- manter a release PyPI/TestPyPI bloqueada;
- preservar rastreabilidade técnica da futura versão `2.0.3`.

## Regra principal

**Nunca use `git add .`, `git add -A` ou qualquer staging amplo equivalente.**

Todo staging deve ser por caminho explícito, depois de inspeção.

Se houver dúvida sobre algum arquivo, deixe-o fora do commit.

## Proibições absolutas

Não faça:

- publicação em PyPI;
- publicação em TestPyPI;
- alteração de versão para `2.0.3`;
- criação de tag;
- push remoto;
- squash automático;
- rebase destrutivo;
- reset destrutivo;
- remoção em massa sem inventário;
- commit de `.env`, chaves, tokens, credenciais ou secrets;
- commit de bases reais, amostras sensíveis, parquet, sqlite, xlsx ou csv sem justificativa explícita;
- commit de `dist/`, `build/`, `.pytest_tmp/`, `.ruff_cache/`, `.mypy_cache/`, `.ipynb_checkpoints/`, `__pycache__/`, `.venv/`, logs, outputs locais ou relatórios temporários;
- commit de arquivos do tipo `pip_freeze*.txt`, `pipdeptree*.txt`, `pip_audit_output.txt`, `changed_files*.txt`, `full_patch*.diff`, salvo se forem movidos conscientemente para uma pasta de evidências documentada e sanitizada — nesta etapa, prefira não commitar esses outputs brutos.

## Parte 1 — Diagnóstico inicial obrigatório

Antes de alterar qualquer coisa, rode:

```bash
git status --short
git branch --show-current
git remote -v
git diff --stat
git diff --name-only
git ls-files --others --exclude-standard | wc -l
git ls-files --others --exclude-standard > .tmp_untracked_inventory.txt
git diff --stat > .tmp_tracked_diff_stat.txt
git diff --name-only > .tmp_tracked_diff_files.txt
```

No Windows PowerShell, se `wc -l` não estiver disponível, use:

```powershell
(git ls-files --others --exclude-standard).Count
git ls-files --others --exclude-standard > .tmp_untracked_inventory.txt
git diff --stat > .tmp_tracked_diff_stat.txt
git diff --name-only > .tmp_tracked_diff_files.txt
```

Depois, analise:

```bash
head -200 .tmp_untracked_inventory.txt
```

No PowerShell:

```powershell
Get-Content .tmp_untracked_inventory.txt -TotalCount 200
```

Produza um resumo com:

- branch atual;
- quantidade aproximada de untracked;
- principais grupos de arquivos untracked;
- arquivos tracked modificados;
- arquivos claramente seguros;
- arquivos claramente proibidos;
- arquivos duvidosos.

Não faça commit ainda.

## Parte 2 — Varredura de sigilos e dados sensíveis

Faça uma busca conservadora em arquivos tracked modificados e nos candidatos a commit.

Procure padrões como:

- `API_KEY`
- `API_SECRET`
- `SECRET`
- `TOKEN`
- `PASSWORD`
- `PASSWD`
- `PRIVATE KEY`
- `BEGIN RSA PRIVATE KEY`
- `BEGIN OPENSSH PRIVATE KEY`
- `BINANCE_API_KEY`
- `BINANCE_API_SECRET`
- `AWS_ACCESS_KEY_ID`
- `GOOGLE_APPLICATION_CREDENTIALS`
- `OPENAI_API_KEY`
- `sk-`
- URLs com usuário/senha embutidos
- caminhos locais contendo usuários, se forem desnecessários
- dados pessoais identificáveis
- CPFs, CNPJs, e-mails reais, telefones, nomes de clientes ou contratos reais

Comandos sugeridos:

```bash
git diff -- . ':!*.lock' | grep -Ei "API_KEY|API_SECRET|SECRET|TOKEN|PASSWORD|PASSWD|PRIVATE KEY|BEGIN RSA|BEGIN OPENSSH|BINANCE|AWS_ACCESS_KEY|GOOGLE_APPLICATION_CREDENTIALS|OPENAI_API_KEY|sk-" || true
```

Se `ripgrep` estiver disponível:

```bash
rg -n --hidden --glob '!*.lock' --glob '!dist/**' --glob '!build/**' --glob '!.git/**' "API_KEY|API_SECRET|SECRET|TOKEN|PASSWORD|PASSWD|PRIVATE KEY|BEGIN RSA|BEGIN OPENSSH|BINANCE|AWS_ACCESS_KEY|GOOGLE_APPLICATION_CREDENTIALS|OPENAI_API_KEY|sk-" .
```

Se encontrar qualquer candidato sensível:

1. Não commite.
2. Informe o arquivo e o tipo de risco.
3. Sugira remover, anonimizar ou mover para `.gitignore`.
4. Se o segredo já estiver tracked historicamente, não tente resolver histórico agora; apenas informe claramente.

## Parte 3 — Melhorar `.gitignore` com segurança

Inspecione o `.gitignore` atual.

Atualize-o de forma conservadora para ignorar artefatos comuns, sem esconder arquivos-fonte relevantes.

Inclua, se ainda não existirem, padrões como:

```gitignore
# Python caches
__pycache__/
*.py[cod]
*$py.class

# Virtual environments
.venv/
venv/
env/
ENV/

# Build artifacts
build/
dist/
*.egg-info/
.eggs/

# Test and quality caches
.pytest_cache/
.pytest_tmp/
.coverage
coverage.xml
htmlcov/
.ruff_cache/
.mypy_cache/
.tox/

# Jupyter
.ipynb_checkpoints/

# Local environment and secrets
.env
.env.*
*.env
*.pem
*.key
*.crt
*.p12
*.pfx
secrets/
.secret/

# Local logs and temporary files
*.log
*.tmp
*.bak
*.swp
.tmp_*

# Local diagnostic outputs
pip_audit_output*.txt
pip_freeze*.txt
pipdeptree*.txt
pip_check_output*.txt
changed_files*.txt
full_patch*.diff
.tmp_untracked_inventory.txt
.tmp_tracked_diff_stat.txt
.tmp_tracked_diff_files.txt

# Local datasets and heavy outputs
*.parquet
*.feather
*.sqlite
*.sqlite3
*.db
*.duckdb
*.pkl
*.pickle
*.joblib

# Optional local reports/exports
reports/local/
outputs/local/
artifacts/local/
```

Atenção:

- Não ignore genericamente `*.csv`, `*.xlsx` ou `*.json` sem avaliar, porque o projeto pode ter fixtures, exemplos ou configurações versionáveis.
- Se existirem dados pequenos e sintéticos usados por testes, eles podem ser versionáveis, mas devem ficar em pasta controlada como `tests/fixtures/`.
- Se o `.gitignore` tiver regra ampla perigosa, como `*.json`, avalie se ela está escondendo arquivos importantes de configuração. Não remova sem entender, mas sinalize.

Depois de editar `.gitignore`, rode:

```bash
git status --short
git ls-files --others --exclude-standard | wc -l
```

No PowerShell:

```powershell
(git ls-files --others --exclude-standard).Count
```

Informe se os 10k untracked caíram e quais grupos continuam visíveis.

## Parte 4 — Classificação dos arquivos para commit

Classifique os arquivos em quatro grupos:

### Grupo A — Deve commitar

Arquivos-fonte, testes, docs e workflows diretamente relacionados ao hardening:

- `riskbands/strategies/categorical.py`
- `riskbands/binning_engine.py`
- `riskbands/reporting.py`
- `riskbands/utils/dtypes.py`
- `tests/test_categorical_regressions.py`
- `tests/test_export_bundle_security.py`
- `tests/test_force_numeric.py`
- `pyproject.toml`
- `.github/workflows/tests.yml`
- `.github/workflows/release-validation.yml`
- `docs/supply_chain_dependencies.md`
- `.gitignore`, se alterado com segurança

### Grupo B — Pode commitar se fizer sentido

- README/docs alterados intencionalmente;
- fixtures sintéticas pequenas usadas por testes;
- arquivos de configuração necessários ao build/docs;
- changelog técnico local, se existir e não for release final.

### Grupo C — Não commitar

- `dist/`
- `build/`
- `.pytest_tmp/`
- `.ruff_cache/`
- `.mypy_cache/`
- `.venv/`
- `__pycache__/`
- `.ipynb_checkpoints/`
- logs;
- relatórios temporários;
- outputs de auditoria brutos;
- arquivos `pip_freeze`, `pipdeptree`, `pip_audit_output`, `changed_files`, `full_patch`;
- datasets locais;
- planilhas locais;
- notebooks de exploração não revisados;
- qualquer arquivo com segredo ou dado real.

### Grupo D — Duvidosos

Tudo que não couber claramente nos grupos anteriores.

Para Grupo D:

- não commitar;
- listar no relatório final;
- sugerir decisão futura.

## Parte 5 — Plano de commits segmentados

Faça os commits em partes pequenas e coerentes.

Não use staging amplo. Use apenas caminhos explícitos.

### Commit 1 — Testes de regressão P1

Conteúdo esperado:

```bash
git add tests/test_categorical_regressions.py tests/test_export_bundle_security.py
git commit -m "Add regression tests for categorical and bundle export safety"
```

Antes de commitar, valide:

```bash
git diff --cached --stat
git diff --cached --name-only
git diff --cached --check
```

### Commit 2 — Correção do fluxo categórico

Conteúdo esperado:

```bash
git add riskbands/strategies/categorical.py riskbands/binning_engine.py
git commit -m "Harden categorical binning transform behavior"
```

Antes de commitar, valide o diff staged e rode, se viável:

```bash
python -m pytest -q tests/test_categorical_regressions.py --basetemp=.pytest_tmp/commit_categorical
```

### Commit 3 — Export seguro do bundle

Conteúdo esperado:

```bash
git add riskbands/reporting.py
git commit -m "Sanitize bundle export artifact paths"
```

Antes de commitar, rode:

```bash
python -m pytest -q tests/test_export_bundle_security.py --basetemp=.pytest_tmp/commit_export_security
```

### Commit 4 — `force_numeric`

Conteúdo esperado:

```bash
git add riskbands/utils/dtypes.py riskbands/binning_engine.py tests/test_force_numeric.py
git commit -m "Implement force_numeric dtype override"
```

Atenção:

Se `riskbands/binning_engine.py` já foi parcialmente commitado no Commit 2, use staging interativo ou revise cuidadosamente para que este commit contenha apenas as partes de `force_numeric`.

Se não for seguro separar por hunk, é aceitável consolidar Commit 2 e Commit 4 em um único commit técnico, mas explique isso no relatório final.

Validação:

```bash
python -m pytest -q tests/test_force_numeric.py --basetemp=.pytest_tmp/commit_force_numeric
```

### Commit 5 — Quality gates

Conteúdo esperado:

```bash
git add pyproject.toml .github/workflows/tests.yml .github/workflows/release-validation.yml
git commit -m "Strengthen CI quality and security gates"
```

Validação:

```bash
python -m ruff check riskbands tests
python -m bandit -q -r riskbands
python -m pytest -q --basetemp=.pytest_tmp/commit_quality --cov=riskbands --cov-report=term-missing
```

### Commit 6 — Supply chain constraints e documentação

Conteúdo esperado:

```bash
git add pyproject.toml docs/supply_chain_dependencies.md
git commit -m "Constrain solver dependencies to avoid vulnerable protobuf"
```

Atenção:

Se `pyproject.toml` já foi parcialmente commitado no Commit 5, use staging interativo para separar quality gates de constraints runtime.

Se não for seguro separar por hunk, consolide Commit 5 e Commit 6 em um único commit e explique a razão.

Validação:

```bash
python -m pip check
python -m pip_audit
python -m pytest -q --basetemp=.pytest_tmp/commit_supply_chain --cov=riskbands --cov-report=term-missing
```

### Commit 7 — `.gitignore` e limpeza de workspace

Conteúdo esperado:

```bash
git add .gitignore
git commit -m "Ignore local caches diagnostics and sensitive artifacts"
```

Só faça este commit se `.gitignore` tiver sido alterado.

Não commite outputs temporários de diagnóstico.

## Parte 6 — Validação final após commits

Depois dos commits, rode:

```bash
git status --short
git log --oneline -10
python -m pip check
python -m ruff check riskbands tests
python -m bandit -q -r riskbands
python -m pytest -q --basetemp=.pytest_tmp/final_committed --cov=riskbands --cov-report=term-missing
python -m pip_audit
python -m build
python -m twine check dist/*
```

Depois do build, confirme que `dist/` continua untracked/ignorado e não será commitado.

## Parte 7 — Relatório final obrigatório

Responda em português com:

1. Branch atual.
2. Quantidade inicial aproximada de untracked.
3. Quantidade final aproximada de untracked após `.gitignore`.
4. Arquivos classificados como seguros e commitados.
5. Arquivos deixados de fora por segurança.
6. Arquivos duvidosos que precisam de decisão humana.
7. Lista dos commits criados, com hash curto e mensagem.
8. Resultado dos testes/checks finais.
9. Confirmação explícita de que não houve push.
10. Confirmação explícita de que não houve publicação PyPI/TestPyPI.
11. Confirmação explícita de que nenhum arquivo sensível foi commitado, ou lista de alertas se houver risco.
12. Próximo passo recomendado para preparar a release candidate `2.0.3`.

## Critério de sucesso

Esta etapa só é considerada bem-sucedida se:

- nenhum arquivo sensível for commitado;
- nenhum dado local pesado ou temporário for commitado;
- os commits forem pequenos e coerentes;
- `.gitignore` reduzir significativamente os untracked irrelevantes;
- os testes e checks relevantes continuarem passando;
- PyPI/TestPyPI continuarem bloqueados;
- a worktree ficar compreensível para a próxima etapa de release candidate.
