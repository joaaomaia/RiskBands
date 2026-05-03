# Auditoria pós-commit, assets/imagens, README e prontidão para release candidate RiskBands

Você está trabalhando no repositório local do projeto **RiskBands**.

Caminho esperado do repositório:

```text
D:\0_CienciaDados\1_Frameworks\RiskBands
```

## Contexto

O projeto passou por uma etapa de hardening antes de uma futura release patch `2.0.3`. Já foram tratados pontos importantes:

- correções P1 de fluxo categórico;
- correções P1 de segurança no `export_bundle` contra path traversal;
- implementação de `force_numeric`;
- reforço de CI com `ruff`, `pytest-cov`, `bandit`, `pip-audit`, `pip check`;
- correção de supply chain envolvendo `optbinning`, `ortools` e `protobuf`;
- limpeza de worktree e melhoria de `.gitignore`;
- criação de commits locais, sem push, sem tag, sem publicação em PyPI/TestPyPI.

Estado informado anteriormente:

```text
git status --short limpo
sem push
sem tag
sem alteração de versão para 2.0.3
testes passando em venv limpo
pip-audit sem vulnerabilidades conhecidas
```

Commits recentes informados:

```text
7cdd29f Constrain solver dependencies to avoid vulnerable protobuf
37e8f94 Strengthen CI quality and security gates
2455912 Ignore local caches diagnostics and sensitive artifacts
```

Agora preciso de uma **auditoria pós-commit extremamente cuidadosa**, antes de preparar qualquer release candidate.

## Objetivo

Executar uma auditoria pós-commit para responder:

1. A worktree está realmente limpa e segura?
2. Algum arquivo sensível, pesado, temporário ou local ficou versionado?
3. Os commits recentes estão coerentes e rastreáveis?
4. As imagens/assets ignorados no `.gitignore` são usados por README, docs ou site?
5. O `.gitignore` precisa de ajustes finos para não bloquear fixtures sintéticas legítimas nem assets oficiais?
6. O `README.md` precisa de melhorias depois dos patches recentes?
7. O projeto está pronto para uma etapa separada de release candidate `2.0.3`, sem ainda fazer version bump?

## Regras obrigatórias

- Não faça push.
- Não crie tag.
- Não publique em PyPI.
- Não publique em TestPyPI.
- Não altere versão para `2.0.3` nesta etapa.
- Não altere `RELEASE.md` para release final nesta etapa, salvo se for apenas apontar achado no relatório.
- Não use `git add .`.
- Não use `git add -A`.
- Não apague arquivos de imagem, docs, assets, dados ou outputs sem produzir antes um relatório claro e justificativa.
- Não delete arquivos apenas porque estão ignorados.
- Não comite nada automaticamente antes de apresentar o relatório final da auditoria.
- Se fizer qualquer alteração pequena e segura, ela deve ser feita só depois da auditoria e deve ser claramente listada.
- Se houver dúvida sobre um arquivo, classifique como **duvidoso** e não altere/remova.

## Fase 1 — Auditoria Git e worktree

Execute e registre:

```bash
git status --short
git status --ignored --short
git log --oneline --decorate -n 12
git diff --stat HEAD~3..HEAD
git show --stat --oneline HEAD~2..HEAD
git branch --show-current
```

Verifique se a branch atual é a esperada. Se estiver em `master`, apenas registre. Não crie branch automaticamente sem necessidade.

Classifique o estado da worktree:

```text
LIMPA
SUJA MAS SEGURA
SUJA COM RISCO
INDETERMINADA
```

Explique o motivo.

## Fase 2 — Auditoria de arquivos versionados potencialmente sensíveis ou pesados

Procure arquivos versionados com extensões sensíveis ou suspeitas:

```bash
git ls-files | grep -Ei "(\.env$|\.pem$|\.key$|\.crt$|\.p12$|\.pfx$|\.csv$|\.xlsx$|\.parquet$|\.feather$|\.sqlite$|\.sqlite3$|\.db$|\.duckdb$|\.pkl$|\.pickle$|\.joblib$|\.zip$|\.7z$|\.rar$|\.tar$|\.gz$|\.ai$|\.psd$)" || true
```

No PowerShell, se necessário:

```powershell
git ls-files | Select-String -Pattern "\.env$|\.pem$|\.key$|\.crt$|\.p12$|\.pfx$|\.csv$|\.xlsx$|\.parquet$|\.feather$|\.sqlite$|\.sqlite3$|\.db$|\.duckdb$|\.pkl$|\.pickle$|\.joblib$|\.zip$|\.7z$|\.rar$|\.tar$|\.gz$|\.ai$|\.psd$"
```

Procure arquivos grandes versionados:

```powershell
git ls-files | ForEach-Object {
    $item = Get-Item $_ -ErrorAction SilentlyContinue
    if ($item -and $item.Length -gt 5MB) {
        "$($_) $([math]::Round($item.Length / 1MB, 2)) MB"
    }
}
```

Classifique cada achado em:

```text
SEGURO
PROIBIDO
DÚVIDA
```

Critérios:

- `PROIBIDO`: segredo, credencial, dataset real, output local, modelo serializado, banco local, build, cache, arquivo pesado sem justificativa.
- `DÚVIDA`: fixture, imagem, planilha, CSV sintético ou asset que pode ser legítimo, mas precisa de confirmação.
- `SEGURO`: arquivo pequeno, sintético, documentado, necessário para testes/docs, sem conteúdo sensível.

Não remova nada nesta fase. Apenas reporte.

## Fase 3 — Varredura simples de sigilos

Faça uma busca conservadora por padrões comuns de segredos, evitando exagerar em falsos positivos.

Sugestões:

```bash
git grep -n -I -E "(AKIA[0-9A-Z]{16}|SECRET_ACCESS_KEY|AWS_SECRET|BINANCE_API_KEY|BINANCE_API_SECRET|OPENAI_API_KEY|sk-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9_]{20,}|-----BEGIN (RSA |EC |OPENSSH |)PRIVATE KEY-----|password\s*=|passwd\s*=|token\s*=|api_key\s*=|secret\s*=)" || true
```

Se houver muitos falsos positivos, separe:

```text
falso positivo
sentinela/teste
risco real
indeterminado
```

Não imprima valores sensíveis completos se encontrar algo real. Mascare o valor.

## Fase 4 — Auditoria do `.gitignore`

Leia o `.gitignore` atual e avalie:

1. Ele protege bem contra commits de:
   - ambientes virtuais;
   - caches;
   - outputs locais;
   - dados tabulares reais;
   - modelos serializados;
   - arquivos de build;
   - segredos;
   - diagnósticos locais?

2. Ele está bloqueando algo que talvez devesse ser versionado?
   - fixtures sintéticas em `tests/fixtures/`;
   - fixtures sintéticas em `tests/data/`;
   - assets oficiais usados por README/docs/site;
   - prompts de governança que deveriam ser documentação;
   - imagens oficiais da marca/projeto.

Atenção especial às regras amplas:

```gitignore
*.csv
*.xlsx
imgs/png/
imgs/svg/
docs/prompts/
riskbands.png
```

Avalie se vale propor exceções como:

```gitignore
!tests/fixtures/**/*.csv
!tests/fixtures/**/*.xlsx
!tests/data/**/*.csv
!tests/data/**/*.xlsx
!docs/assets/**
!docs-site/src/assets/**
```

Mas não aplique automaticamente sem justificar.

## Fase 5 — Auditoria de imagens e assets

O repositório contém ou já conteve referências a imagens como:

```text
riskbands.png
imgs/png/
imgs/svg/
imgs/olds/
imgs/riskbands_logo_reconstruction_bundle/
imgs/riskbands_vector_reconstruction_bundle/
riskbands_vector_reconstruction_bundle.zip
riskbands_master_final.ai
riskbands_master.ai
```

Objetivo: descobrir se imagens/assets ignorados ainda são referenciados por README, documentação ou site.

Execute buscas como:

```bash
git grep -n "riskbands.png" || true
git grep -n "imgs/png" || true
git grep -n "imgs/svg" || true
git grep -n "imgs/" README.md docs docs-site .github || true
git grep -n "social" README.md docs docs-site .github || true
git grep -n "preview" README.md docs docs-site .github || true
git grep -n "logo" README.md docs docs-site .github || true
```

Se `docs-site/` estiver ignorado localmente ou não versionado, registre isso claramente.

Para cada referência encontrada, responder:

- arquivo que referencia;
- caminho referenciado;
- o arquivo referenciado existe no repositório versionado?
- o arquivo existe apenas localmente/ignorado?
- a referência está quebrada?
- a imagem parece oficial ou artefato temporário?
- recomendação: manter, mover para `docs/assets/`, corrigir link, remover referência, ou deixar como está.

Não mover imagens automaticamente nesta fase, salvo se for claramente seguro e listado como alteração opcional no final.

## Fase 6 — Auditoria do README.md

Leia o `README.md` atual e avalie melhorias depois dos patches recentes.

Verificar se o README explica claramente:

1. O que é o RiskBands.
2. Para que serve em risco de crédito.
3. Instalação.
4. Exemplo mínimo de uso.
5. Exemplo com variáveis categóricas.
6. Exemplo ou menção a `force_numeric` e `force_categorical`.
7. Uso de `export_bundle` e segurança/auditabilidade dos artefatos.
8. Uso opcional de Optuna.
9. Interpretação dos principais outputs.
10. Compatibilidade/dependências relevantes, se necessário.
11. Status do projeto sem prometer maturidade maior do que os gates sustentam.
12. Links de documentação, PyPI e GitHub Pages, se existirem.
13. Imagens quebradas ou links quebrados.

Classifique problemas do README em:

```text
P1 = confunde usuário ou documenta comportamento incorreto
P2 = lacuna importante para adoção
P3 = melhoria editorial
```

Se houver melhorias pequenas e seguras, proponha patch, mas não aplique sem listar antes.

## Fase 7 — Rodar gates finais de auditoria local

Use ambiente limpo ou o venv dedicado já validado no projeto. Não use ambiente global Anaconda se ele tiver conflitos externos.

Rode:

```bash
python -m pip check
python -m pip_audit
python -m ruff check riskbands tests
python -m bandit -q -r riskbands
python -m pytest -q --cov=riskbands --cov-report=term-missing --basetemp .pytest_tmp/post_commit_audit
python -m build
python -m twine check dist/*
```

Se algum comando falhar por ambiente, explique a causa e, se possível, rode em venv limpo.

## Fase 8 — Avaliar coerência dos commits recentes

Analise os commits recentes:

```bash
git log --oneline -n 10
git show --stat 7cdd29f
git show --stat 37e8f94
git show --stat 2455912
```

Se os hashes forem diferentes no ambiente atual, use os três commits mais recentes relacionados ao hardening.

Responder:

- Os commits estão bem separados por tema?
- Algum commit mistura mudança funcional, CI e `.gitignore` demais?
- Essa mistura é aceitável ou recomenda rebase/squash/split antes de push?
- Há risco de perder rastreabilidade?
- Vale reescrever histórico local antes de push ou manter como está?

Não execute rebase automaticamente. Apenas recomende.

## Fase 9 — Opcional: aplicar correções pequenas e seguras

Só depois da auditoria completa, se encontrar melhorias triviais e seguras, você pode aplicar alterações pequenas, por exemplo:

- ajustar `.gitignore` com exceções para fixtures sintéticas;
- corrigir referência quebrada óbvia no README;
- adicionar nota curta no README sobre `force_numeric`;
- adicionar nota curta sobre export auditável;
- mover recomendação para relatório sem mover arquivos.

Regras para alterações opcionais:

- Não mexer em versão.
- Não mexer em publish workflows.
- Não apagar assets.
- Não adicionar arquivos pesados.
- Não adicionar dados reais.
- Não commitar automaticamente.
- Mostrar `git diff --stat` e `git diff` resumido ao final.

## Saída esperada

Responda em português com a seguinte estrutura:

```markdown
# Auditoria pós-commit RiskBands

## 1. Resumo executivo

## 2. Estado Git e worktree
- branch
- status
- untracked
- ignored relevante
- classificação do estado

## 3. Auditoria de arquivos sensíveis, pesados e locais
Tabela com:
- arquivo
- categoria
- classificação
- recomendação

## 4. Varredura de sigilos
- achados reais
- falsos positivos
- ações recomendadas

## 5. Avaliação do .gitignore
- pontos fortes
- riscos
- exceções recomendadas
- alterações sugeridas

## 6. Auditoria de imagens e assets
Tabela com:
- referência
- arquivo que referencia
- existe versionado?
- existe local ignorado?
- risco
- recomendação

## 7. Avaliação do README.md
- pontos fortes
- problemas P1/P2/P3
- melhorias recomendadas
- patch sugerido, se aplicável

## 8. Resultado dos gates locais
Tabela com:
- comando
- resultado
- observação

## 9. Coerência dos commits recentes
- análise dos commits
- recomendação: manter, splitar, squashar ou rebasear

## 10. Alterações opcionais aplicadas nesta etapa
- listar arquivos alterados
- explicar por que eram seguras
- se nenhuma alteração foi feita, dizer explicitamente

## 11. Próximo passo recomendado
- bloquear ou liberar preparação de release candidate 2.0.3
- pendências antes do version bump
```

## Critério de sucesso

A auditoria será considerada bem-sucedida se:

- não houver push/tag/publicação;
- nenhum segredo real for encontrado ou, se encontrado, for reportado com valor mascarado;
- nenhum arquivo pesado/sensível estiver indevidamente versionado;
- imagens e assets usados por README/docs/site forem classificados;
- `.gitignore` tiver recomendações claras;
- README tiver recomendações objetivas;
- gates locais forem reportados;
- houver decisão clara sobre seguir ou não para release candidate `2.0.3`.
