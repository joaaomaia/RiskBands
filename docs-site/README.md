# Site de documentacao do RiskBands

Este diretorio contem o site oficial de documentacao do RiskBands, construido
com Astro e Starlight.

## Desenvolvimento local

```bash
cd docs-site
npm install
npm run dev
```

O servidor local normalmente sobe em `http://localhost:4321`.

## Build de producao

```bash
cd docs-site
npm install
npm run build
```

A saida estatica eh gerada em `docs-site/dist/`.

Para servir localmente a saida buildada:

```bash
cd docs-site
npm run preview
```

## Publicacao

O deploy no GitHub Pages eh feito por `.github/workflows/docs-deploy.yml`.

- pushes em `master` disparam build e deploy da docs
- o workflow faz `npm ci` dentro de `docs-site/`
- o build roda com `npm run build` dentro de `docs-site/`
- o artifact publicado vem de `docs-site/dist/`
- o GitHub Pages deve estar configurado para **GitHub Actions**

## Release do pacote

O repositorio tambem possui workflows de release:

- `.github/workflows/release-validation.yml`
- `.github/workflows/publish-testpypi.yml`
- `.github/workflows/publish-pypi.yml`

Fluxo resumido:

1. atualizar `pyproject.toml`
2. validar localmente com `pytest`, `python -m build` e `python -m twine check dist/*`
3. criar a tag `vX.Y.Z`
4. disparar a publicacao sobre essa tag

Os workflows de publicacao usam Trusted Publishing e validam se a tag bate com
a versao do pacote antes de enviar artefatos.

## Checklist de publicacao

Antes de anunciar a docs publicamente, vale confirmar:

1. GitHub Pages configurado em `Settings > Pages` com `Source = GitHub Actions`.
2. URL final da docs validada apos o primeiro deploy.
3. Home, benchmark e Quickstart abrindo corretamente.
4. Social preview da docs apontando para a imagem esperada.
5. `DOCS_SITE_URL` e `DOCS_BASE_PATH` coerentes com a URL publica.

## Suporte futuro a dominio customizado

O site ja esta preparado para dominio customizado.

- `DOCS_SITE_URL` controla o valor de `site` em `astro.config.mjs`
- `DOCS_BASE_PATH` controla o `base`

Para um dominio como `docs.riskbands.dev`, use:

- `DOCS_SITE_URL=https://docs.riskbands.dev`
- `DOCS_BASE_PATH=/`

e adicione `public/CNAME` com o dominio final quando o corte de DNS estiver
pronto.

## Regenerando os assets do benchmark

As figuras reais usadas na Home e nas paginas metodologicas sao exportadas a
partir do benchmark Python para:

`docs-site/public/benchmark-assets/`

Comando recomendado:

```bash
C:\Users\JM\AppData\Local\anaconda3\python.exe examples\pd_vintage_benchmark\pd_vintage_benchmark.py --all-scenarios --samples-per-period 180 --export-html-dir docs-site\public\benchmark-assets
```

## Como adicionar novas paginas

As paginas da documentacao vivem em:

`docs-site/src/content/docs/`

Estrutura recomendada:

- `technical/` para instalacao, uso, API e exemplos
- `methodology/` para benchmark e paginas conceituais
- `reference/` para release notes e publicacoes
- `project/` para manutencao e contribuicao
