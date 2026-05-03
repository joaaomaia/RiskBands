# Ajustes pré-RC de README, `.gitignore`, assets e governança RiskBands

Você está trabalhando no repositório local do projeto **RiskBands**.

## Objetivo

Executar uma etapa curta, conservadora e auditável de ajustes pré-release-candidate, com foco em:

1. confirmar o estado remoto/local do Git;
2. resolver a política de `docs/prompts/`;
3. ajustar `.gitignore` com exceções seguras para fixtures sintéticas e assets oficiais;
4. revisar assets/imagens oficiais versus locais/ignorados;
5. melhorar o `README.md` com informações relevantes após o hardening;
6. rodar os gates locais;
7. criar commit pequeno e explícito apenas se houver mudanças seguras e justificadas.

Esta etapa **não** é release candidate ainda.

## Proibições absolutas

- Não faça `push`.
- Não crie tag.
- Não publique em PyPI.
- Não publique em TestPyPI.
- Não altere versão para `2.0.3` ainda.
- Não altere `RELEASE.md` nesta etapa, exceto se encontrar erro crítico factual que precise ser corrigido; nesse caso, justifique antes.
- Não rode `git add .`.
- Não rode `git add -A`.
- Não delete assets automaticamente.
- Não versionar dados reais, arquivos `.env`, chaves, certificados, bancos locais, pickles, modelos serializados, outputs, caches, `dist/`, `build/`, `.coverage`, `.pytest_tmp/`, ambientes virtuais ou diagnósticos locais.

## Contexto atual conhecido

A auditoria pós-commit anterior reportou:

- `git status --short` limpo.
- Gates locais passando.
- `pip-audit` sem vulnerabilidades conhecidas após constraints de supply chain.
- `pytest`: `73 passed`, cobertura aproximada `79.17%`.
- `npm --prefix docs-site run build`: passou.
- Assets oficiais do docs-site parecem estar em:
  - `docs-site/public/og/riskbands-social-preview.png`
  - `docs-site/public/brand/*.svg`
  - `docs-site/src/assets/riskbands-*.svg`
- `imgs/social_preview.png` existe versionado, mas parece duplicado ou sem referência direta.
- `riskbands.png`, `imgs/png`, `imgs/svg`, `imgs/olds` estão ignorados e não parecem referenciados diretamente.
- `docs/prompts/prompt_1...prompt_4` já estariam versionados, enquanto `prompt_5...prompt_9` estariam ignorados por regra ampla `docs/prompts/`, gerando inconsistência.
- O README tem espaço para melhorias sobre:
  - suporte atual a `pandas`;
  - não suporte nativo a `PySpark DataFrame`;
  - estratégia recomendada para bases grandes com Spark;
  - variáveis categóricas;
  - `force_numeric` e `force_categorical`;
  - `export_bundle` seguro/sanitizado;
  - link direto para PyPI;
  - nota curta de supply chain/solver dependencies.

## Parte 1 — Confirmar estado Git e remoto/local

Rode:

```bash
git status --short
git branch --show-current
git log --oneline --decorate -n 10
git remote -v
git rev-parse HEAD
git rev-parse origin/master
```

Se for seguro e não modificar nada, rode também:

```bash
git ls-remote origin refs/heads/master
```

Objetivo:

- Confirmar se `origin/master` local aponta para `HEAD` porque houve fetch/push anterior ou apenas porque a ref local está atualizada.
- Não fazer push.
- Não fazer fetch destrutivo.
- Não alterar branch.

Registre no relatório:

- branch atual;
- HEAD;
- `origin/master` local;
- `origin/master` remoto via `ls-remote`, se disponível;
- se o repo está ahead/behind.

## Parte 2 — Revisar `.gitignore` com política segura

Analise o `.gitignore` atual.

### Ajustes desejados

Adicionar exceções seguras para fixtures sintéticas pequenas, sem liberar dados reais em bloco:

```gitignore
# Synthetic fixtures allowed for tests
!tests/fixtures/**/*.csv
!tests/fixtures/**/*.xlsx
!tests/data/**/*.csv
!tests/data/**/*.xlsx
```

Adicionar exceções ou garantias para assets oficiais já versionados:

```gitignore
# Official documentation assets
!docs/assets/**
!docs-site/src/assets/**
!docs-site/public/brand/**
!docs-site/public/og/**
```

Adicionar proteção explícita extra para ambientes locais:

```gitignore
.env.local
.envrc
```

### Política para `docs/prompts/`

Não manter a regra ampla `docs/prompts/` se ela cria inconsistência com prompts já versionados.

Escolha uma política clara:

Opção preferida:

```gitignore
# Local/unreviewed prompts only
/docs/prompts/local/
/docs/prompts/tmp/
/docs/prompts/drafts/
```

Assim, prompts aprovados podem ser versionados em `docs/prompts/`, enquanto rascunhos e prompts locais continuam ignorados.

Se escolher outra política, justifique.

### Não liberar em bloco

Não remova proteções amplas de:

```gitignore
*.csv
*.xlsx
*.parquet
*.pkl
*.pickle
*.joblib
*.db
*.sqlite
*.duckdb
.env
.env.*
*.env
*.pem
*.key
secrets/
```

Apenas use exceções explícitas para caminhos seguros.

## Parte 3 — Auditar assets/imagens

Rode buscas por referências:

```bash
git grep -n "riskbands.png" || true
git grep -n "imgs/png" || true
git grep -n "imgs/svg" || true
git grep -n "imgs/social_preview.png" || true
git grep -n "riskbands-social-preview" || true
git grep -n "riskbands-light" || true
git grep -n "riskbands-dark" || true
git grep -n "favicon.svg" || true
```

Liste arquivos de imagem versionados relevantes:

```bash
git ls-files | grep -E '\.(png|svg|jpg|jpeg|webp|ico)$' || true
```

Classifique cada asset relevante como:

- `OFICIAL_USADO`
- `OFICIAL_SEM_REFERENCIA_DIRETA`
- `LOCAL_IGNORADO`
- `DUPLICADO_PROVAVEL`
- `REMOVER_FUTURAMENTE`
- `MANTER`

Não delete nada automaticamente.

Se houver duplicidade óbvia, por exemplo `imgs/social_preview.png` idêntico a `docs-site/public/og/riskbands-social-preview.png`, apenas documente e recomende consolidação futura, salvo se for trivial e seguro remover com confirmação clara por evidência.

## Parte 4 — Melhorar README.md

Faça um patch pequeno e objetivo no `README.md`.

### Requisitos de conteúdo

Adicionar ou ajustar seções curtas sobre:

1. **Tipos de entrada suportados**
   - Declarar que a API atual é orientada a `pandas.DataFrame`/`pandas.Series`.
   - Declarar que `PySpark DataFrame` ainda não é suportado nativamente.
   - Recomendar, para bases grandes em Spark/Databricks: treinar o binning em amostra/aggregate/pandas auditável e aplicar regras exportadas no ambiente distribuído.
   - Não prometer `transform_spark` se ele ainda não existe.

2. **Variáveis categóricas**
   - Mostrar exemplo mínimo com `force_categorical=[...]`.
   - Mencionar tratamento determinístico de categorias raras, missing e unknown se isso já está implementado.

3. **Overrides de tipo**
   - Explicar `force_numeric` e `force_categorical`.
   - Alertar que a mesma coluna não deve estar nos dois.
   - Mostrar exemplo curto:

```python
binner = Binner(
    strategy="supervised",
    force_numeric=["qtd_restritivos"],
    force_categorical=["rating_interno"],
)
```

4. **Export auditável**
   - Mencionar `export_bundle(...)`.
   - Mencionar que nomes de features em artefatos exportados são sanitizados para evitar paths inseguros, mantendo rastreabilidade no manifest.

5. **Supply chain / solver dependencies**
   - Incluir nota curta apontando para `docs/supply_chain_dependencies.md`.
   - Não exagerar tecnicamente no README; deixar detalhes no doc específico.

6. **Link PyPI**
   - Adicionar link direto para o pacote no PyPI, se ainda não houver.

### Estilo do README

- Manter tom profissional e direto.
- Não transformar README em documentação extensa demais.
- Não declarar que `2.0.3` já existe.
- Não declarar suporte a PySpark nativo.
- Não declarar compatibilidade não testada.
- Não remover conteúdo útil existente sem justificativa.

## Parte 5 — Verificar prompts versionados e política de governança

Rode:

```bash
git ls-files docs/prompts || true
git status --ignored --short docs/prompts || true
```

Se `prompt_1...prompt_4` estão versionados e `prompt_5...prompt_9` ignorados, corrija a regra do `.gitignore` conforme política da Parte 2.

Não versionar automaticamente prompts locais ignorados nesta etapa, a menos que sejam claramente documentação oficial do processo e não contenham dados sensíveis.

Se optar por versionar prompts, faça varredura simples antes:

```bash
grep -RInE "(api[_-]?key|secret|token|password|senha|private[_-]?key|BEGIN (RSA|OPENSSH|PRIVATE) KEY)" docs/prompts || true
```

## Parte 6 — Varredura de segurança antes de stage

Antes de qualquer `git add`, rode:

```bash
git status --short
git diff --stat
git diff -- README.md .gitignore
```

Verifique arquivos suspeitos versionados:

```bash
git ls-files | grep -Ei '\.(env|pem|key|p12|pfx|csv|xlsx|parquet|pkl|pickle|joblib|sqlite|sqlite3|db|duckdb|zip|7z|rar)$' || true
```

Verifique arquivos grandes versionados:

```bash
git ls-files | while read f; do
  if [ -f "$f" ]; then
    size=$(wc -c < "$f")
    if [ "$size" -gt 5242880 ]; then
      echo "$f $size"
    fi
  fi
done
```

Procure segredos nas mudanças:

```bash
git diff | grep -Ein "(api[_-]?key|secret|token|password|senha|private[_-]?key|BEGIN (RSA|OPENSSH|PRIVATE) KEY)" || true
```

## Parte 7 — Staging e commit opcional

Se houver apenas mudanças seguras em `README.md` e `.gitignore`, fazer staging explícito:

```bash
git add README.md .gitignore
```

Se houver mudança opcional segura em docs de assets ou docs de supply chain, staged por caminho explícito, por exemplo:

```bash
git add docs/supply_chain_dependencies.md
```

Não adicionar artefatos gerados.

Commit sugerido:

```bash
git commit -m "Document pre-release usage and tighten ignore policy"
```

Só crie commit se:

- `git diff --cached --stat` contiver apenas arquivos esperados;
- nenhum arquivo sensível entrar no índice;
- nenhum artefato pesado entrar no índice;
- os gates passarem.

Se não houver mudança necessária, não crie commit.

## Parte 8 — Gates finais

Rode em venv limpo/confiável do projeto:

```bash
python -m pip check
python -m pip_audit
python -m ruff check riskbands tests
python -m bandit -q -r riskbands
python -m pytest -q --cov=riskbands --cov-report=term-missing --basetemp .pytest_tmp/pre_rc_readme_gitignore
python -m build
python -m twine check dist/*
```

Se `docs-site` estiver disponível:

```bash
npm --prefix docs-site run build
```

Se algum gate falhar por razão externa ao projeto, registre claramente, mas não maquie o resultado.

## Parte 9 — Resultado esperado da resposta

Responda em português com:

1. resumo executivo;
2. branch, HEAD e estado remoto/local;
3. mudanças aplicadas no `.gitignore`;
4. política final para `docs/prompts/`;
5. achados sobre assets/imagens;
6. mudanças aplicadas no README;
7. arquivos staged/commitados;
8. hash do commit, se criado;
9. gates executados e resultados;
10. confirmação explícita de:
    - sem push;
    - sem tag;
    - sem PyPI/TestPyPI;
    - sem version bump;
    - sem arquivos sensíveis commitados;
11. recomendação objetiva:
    - liberar preparação do RC `2.0.3`; ou
    - bloquear e listar pendências.

## Critério de aceite

A etapa só é considerada concluída se:

- `git status --short` estiver limpo ao final;
- README estiver mais claro sem prometer suporte inexistente;
- `.gitignore` estiver mais seguro e menos inconsistente;
- assets oficiais não forem quebrados;
- gates principais passarem;
- nenhum dado real, segredo, artefato pesado, build output ou cache for commitado;
- nada for publicado.
