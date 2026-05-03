# Reforçar CI, coverage, segurança e dependências do RiskBands

```text
Você está trabalhando no projeto RiskBands.

Contexto atual:
- Os testes P1 de categóricas foram criados e o fluxo categórico foi corrigido.
- Os testes P1 de segurança do export_bundle foram criados e o export seguro foi corrigido.
- O parâmetro público force_numeric foi implementado e validado.
- A suíte local reportada está verde: 73 passed, 23 warnings.
- Ainda NÃO devemos publicar em PyPI ou TestPyPI.
- Esta etapa deve reforçar qualidade, automação, coverage, lint, segurança e consistência de dependências antes de qualquer release 2.0.3.

Objetivo desta etapa:
Atualizar a configuração de desenvolvimento e os workflows para que o projeto tenha gates mínimos de qualidade antes do próximo patch release.

Escopo permitido:
1. Atualizar pyproject.toml.
2. Atualizar workflows de CI e release validation.
3. Adicionar configuração de ferramentas de qualidade, se necessário.
4. Adicionar arquivos auxiliares de constraints/checks, se fizer sentido.
5. Ajustar pequenos problemas simples revelados por lint, desde que não mudem comportamento público.
6. Atualizar ou adicionar testes apenas se necessário para manter a suíte verde.

Fora de escopo:
- Não alterar versão do pacote.
- Não alterar RELEASE.md para nova versão ainda.
- Não publicar em PyPI.
- Não publicar em TestPyPI.
- Não fazer refatoração grande no Binner.
- Não mexer em lógica de binning, categóricas, force_numeric ou export_bundle, salvo se um check revelar erro trivial de import/lint.
- Não remover dependências de runtime nesta etapa sem justificar e testar instalação limpa.

================================================================================
PARTE 1 — Inspeção inicial
================================================================================

Antes de editar, inspecione:
- pyproject.toml
- .github/workflows/tests.yml
- .github/workflows/release-validation.yml
- qualquer workflow de publish, se existir
- estrutura de tests/
- scripts de smoke test

Rode a suíte atual para confirmar baseline:

```bash
python -m pytest -q --basetemp .pytest_tmp/baseline_quality_gate
```

Se o ambiente Windows tiver problema de permissão em diretório temporário padrão, use sempre `--basetemp` dentro do workspace.

================================================================================
PARTE 2 — Atualizar pyproject.toml
================================================================================

Atualize o extra `dev` para incluir ferramentas mínimas de qualidade.

Adicionar, se ainda não existirem:
- pytest-cov
- ruff
- pip-audit
- bandit

Sugestão:

```toml
[project.optional-dependencies]
dev = [
  "build>=1.2",
  "black>=24.4",
  "ipykernel>=6.29",
  "openpyxl>=3.1",
  "plotly>=6.0",
  "pytest>=8.2",
  "pytest-cov>=5",
  "ruff>=0.6",
  "twine>=5.1",
  "pip-audit>=2.7",
  "bandit>=1.7"
]
```

Adicionar configuração mínima do Ruff no pyproject.toml.

Sugestão inicial conservadora:

```toml
[tool.ruff]
target-version = "py310"
line-length = 120

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP"]
ignore = []

[tool.ruff.lint.per-file-ignores]
"tests/**/*.py" = ["B018"]
```

Ajuste se necessário, mas mantenha o objetivo de não mascarar problemas importantes.

Adicionar configuração de coverage/pytest-cov.

Sugestão:

```toml
[tool.coverage.run]
source = ["riskbands"]
branch = true

[tool.coverage.report]
show_missing = true
skip_covered = false
fail_under = 70
exclude_lines = [
  "pragma: no cover",
  "if TYPE_CHECKING:",
  "if __name__ == .__main__.:",
]
```

Se `fail_under = 70` quebrar por cobertura atual muito menor, não reduza silenciosamente. Primeiro rode o relatório. Se for impossível atingir agora sem criar muitos testes, use uma estratégia honesta:
- gerar relatório de coverage sem fail_under no primeiro commit; ou
- usar threshold inicial menor com justificativa explícita; ou
- manter 70 como meta, mas não bloquear CI ainda.

Preferência: bloquear em 70% se a suíte atual já permitir.

================================================================================
PARTE 3 — Atualizar tests.yml
================================================================================

Atualize `.github/workflows/tests.yml` para incluir:
- `permissions: contents: read`
- instalação do pacote com extras de dev
- ruff check
- pytest com coverage
- pip check

Manter matriz Python 3.11 e 3.12.

Fluxo sugerido:

```yaml
permissions:
  contents: read

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        python-version: ["3.11", "3.12"]

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install package and test dependencies
        run: |
          python -m pip install --upgrade pip
          python -m pip install -e .[dev]

      - name: Check dependency consistency
        run: python -m pip check

      - name: Lint with ruff
        run: python -m ruff check riskbands tests

      - name: Run test suite with coverage
        run: |
          python -m pytest -q \
            --basetemp .pytest_tmp \
            --cov=riskbands \
            --cov-report=term-missing \
            --cov-report=xml
```

Se o projeto ainda tiver vários problemas simples de Ruff, corrija apenas os problemas mecânicos e seguros:
- imports não usados
- imports duplicados
- f-string sem placeholder
- trailing whitespace
- import ordering

Não faça refatoração comportamental para agradar o Ruff nesta etapa.

================================================================================
PARTE 4 — Atualizar release-validation.yml
================================================================================

O workflow de release-validation já valida build, twine check e smoke wheel/sdist. Reforce-o sem publicar nada.

Adicionar antes do build:
- pip check
- ruff check
- pytest com os testes críticos P1/P2 incluídos

Os testes críticos a incluir no subset de release devem conter, no mínimo:
- tests/test_categorical_regressions.py
- tests/test_export_bundle_security.py
- tests/test_force_numeric.py, se existir
- tests/test_public_api.py
- tests/test_api_usability.py
- tests/test_binning_engine.py
- tests/test_compare.py
- tests/test_examples_smoke.py
- tests/test_stable_score.py
- tests/test_temporal_stability.py

Se o subset ficar redundante, prefira rodar a suíte completa no release-validation:

```bash
python -m pytest -q --basetemp .pytest_tmp_release
```

Adicionar também smoke do extra viz, se o script suportar:

```bash
python -m pip install "dist/*.whl[viz]"
python scripts/smoke_test_installed_package.py --expected-version "${{ needs.validate.outputs.package-version }}" --check-viz
```

Se a sintaxe com glob + extras não funcionar, instale o wheel normal e depois instale o extra local de forma adequada, ou documente a limitação.

================================================================================
PARTE 5 — Segurança: bandit e pip-audit
================================================================================

Adicione checks de segurança de forma prática.

No CI principal, rode pelo menos:

```bash
python -m bandit -q -r riskbands
python -m pip_audit
```

Se `pip-audit` reportar vulnerabilidade transitiva que não pode ser corrigida agora, não ignore silenciosamente. Responda com:
- pacote afetado;
- severidade;
- dependência de origem;
- recomendação;
- se deve bloquear ou apenas documentar nesta etapa.

Se `bandit` apontar falso positivo, use exclusão localizada e justificada, não ignore global amplo.

================================================================================
PARTE 6 — Dependências abertas e compatibilidade
================================================================================

Avalie as dependências runtime no pyproject.toml, especialmente:
- pandas
- numpy
- scikit-learn
- scipy
- optbinning
- optuna
- category_encoders
- matplotlib
- seaborn
- tqdm

Não adicione tetos arbitrários sem evidência.

Nesta etapa, faça pelo menos uma das opções:

Opção A — conservadora:
- manter runtime dependencies como estão;
- adicionar `pip check`, `pip-audit` e CI em Python 3.11/3.12;
- abrir recomendação para matriz min/latest em etapa posterior.

Opção B — mais forte:
- criar arquivo `constraints-dev.txt` ou equivalente;
- documentar que ele é para ambiente de desenvolvimento/CI, não necessariamente runtime;
- não mudar compatibilidade pública sem teste.

Se `category_encoders` não for mais usado depois da correção de categóricas, verifique por busca no código. Se estiver realmente sem uso, NÃO remova automaticamente nesta etapa; apenas reporte como candidato a remoção futura, porque remover dependência runtime é mudança de packaging que precisa smoke específico.

================================================================================
PARTE 7 — Comandos locais obrigatórios
================================================================================

Depois das alterações, rode:

```bash
python -m pip install -e .[dev]
python -m pip check
python -m ruff check riskbands tests
python -m pytest -q --basetemp .pytest_tmp/quality_full --cov=riskbands --cov-report=term-missing
python -m bandit -q -r riskbands
python -m pip_audit
python -m build
python -m twine check dist/*
```

Se `build` gerar artefatos antigos misturados em `dist/`, limpe antes:

```bash
rm -rf dist build *.egg-info
python -m build
python -m twine check dist/*
```

No Windows PowerShell, use o equivalente:

```powershell
Remove-Item -Recurse -Force dist, build, *.egg-info -ErrorAction SilentlyContinue
python -m build
python -m twine check dist\*
```

================================================================================
PARTE 8 — Resultado esperado da resposta
================================================================================

Ao final, responda em português com:

1. Arquivos alterados.
2. Checks adicionados ao pyproject.toml.
3. Workflows alterados.
4. Comandos executados.
5. Resultado de cada comando.
6. Coverage total obtido e principais módulos descobertos.
7. Resultado do Ruff.
8. Resultado do pip check.
9. Resultado do Bandit.
10. Resultado do pip-audit.
11. Resultado do build e twine check.
12. Se alguma ferramenta não pôde rodar, explique por quê e o que falta.
13. Confirmação explícita de que a versão não foi alterada.
14. Confirmação explícita de que nada foi publicado em PyPI/TestPyPI.
15. Próximo passo recomendado.

Critério de sucesso ideal:
- pytest verde;
- ruff verde;
- pip check verde;
- bandit sem high severity;
- pip-audit sem high/critical não tratada;
- build verde;
- twine check verde;
- coverage reportado;
- workflows atualizados sem publish.

Lembre-se:
Esta etapa fortalece os gates de qualidade. Ainda não é etapa de release e ainda não deve publicar nada.
```
