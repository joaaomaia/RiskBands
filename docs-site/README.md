# Site de documentação do RiskBands

Este diretório contém o site oficial de documentação do RiskBands, construído com Astro e Starlight.

## Desenvolvimento local

```bash
cd docs-site
npm install
npm run dev
```

O servidor local normalmente sobe em `http://localhost:4321`.

## Build de produção

```bash
cd docs-site
npm install
npm run build
```

A saída estática é gerada em `docs-site/dist/`.

Para servir localmente a saída buildada:

```bash
cd docs-site
npm run preview
```

## Publicação

O deploy no GitHub Pages é feito por `.github/workflows/docs-deploy.yml`.

- pushes em `master` disparam build e deploy da docs
- o workflow usa a action oficial do Astro para GitHub Pages
- o site é buildado a partir de `docs-site/`

## Checklist de publicação

Antes de anunciar a docs publicamente, vale confirmar:

1. GitHub Pages configurado para publicar via GitHub Actions.
2. URL final da docs validada após o primeiro deploy.
3. Home, benchmark e Quickstart abrindo corretamente.
4. Social preview da docs apontando para a imagem esperada.
5. `DOCS_SITE_URL` e `DOCS_BASE_PATH` coerentes com a URL pública.

## Suporte futuro a domínio customizado

O site já está preparado para domínio customizado.

- `DOCS_SITE_URL` controla o valor de `site` em `astro.config.mjs`
- `DOCS_BASE_PATH` controla o `base`

Para um domínio como `docs.riskbands.dev`, use:

- `DOCS_SITE_URL=https://docs.riskbands.dev`
- `DOCS_BASE_PATH=/`

e adicione `public/CNAME` com o domínio final quando o corte de DNS estiver pronto.

## Regenerando os assets do benchmark

As figuras reais usadas na Home e nas páginas metodológicas são exportadas a partir do benchmark Python para:

`docs-site/public/benchmark-assets/`

Comando recomendado:

```bash
C:\Users\JM\AppData\Local\anaconda3\python.exe examples\pd_vintage_benchmark\pd_vintage_benchmark.py --all-scenarios --samples-per-period 180 --export-html-dir docs-site\public\benchmark-assets
```

## Como adicionar novas páginas

As páginas da documentação vivem em:

`docs-site/src/content/docs/`

Estrutura recomendada:

- `technical/` para instalação, uso, API e exemplos
- `methodology/` para benchmark e páginas conceituais
- `reference/` para release notes e publicações
- `project/` para manutenção e contribuição

Depois de adicionar uma página:

1. ligue a página no sidebar do Starlight em `astro.config.mjs`
2. decida se ela entra melhor pela porta técnica ou pela porta metodológica
3. mantenha as afirmações alinhadas ao que o repositório realmente implementa
