---
title: "Desenvolvimento"
description: "Como manter o site da documentação, adicionar páginas e entender o deploy em GitHub Pages."
---

## Biblioteca versus site da docs

O repositório agora tem duas camadas de documentação:

- `docs/` mantém material Markdown mais leve, já existente no projeto Python
- `docs-site/` é o site oficial em Astro + Starlight pensado para publicação em GitHub Pages

## Fluxo local da documentação

```bash
cd docs-site
npm install
npm run dev
```

Para gerar build de produção:

```bash
cd docs-site
npm install
npm run build
```

## Onde adicionar páginas

Crie páginas em:

`docs-site/src/content/docs/`

Regra prática:

- use `technical/` quando a página ajudar alguém a instalar, rodar ou usar a API
- use `methodology/` quando a página ajudar alguém a entender a tese e a história do benchmark

## Atualizando a navegação

A navegação principal fica em:

`docs-site/astro.config.mjs`

Se você adicionar uma página e quiser deixá-la encontrável, atualize o sidebar do Starlight ali.

## Deploy em GitHub Pages

O deploy está configurado em:

`.github/workflows/docs-deploy.yml`

O workflow:

- roda em pushes para `master`
- builda o site Astro a partir de `docs-site/`
- publica a saída estática no GitHub Pages

## Figuras do benchmark na documentação

Os embeds metodológicos da docs usam assets reais exportados pelo benchmark para:

`docs-site/public/benchmark-assets/`

Comando de regeneração:

```bash
C:\Users\JM\AppData\Local\anaconda3\python.exe examples\pd_vintage_benchmark\pd_vintage_benchmark.py --all-scenarios --samples-per-period 180 --export-html-dir docs-site\public\benchmark-assets
```

Isso mantém a Home e as páginas metodológicas conectadas a saídas reais do repositório, e não a mockups.

## Domínio customizado no futuro

A configuração do Astro já está parametrizada para:

- `DOCS_SITE_URL`
- `DOCS_BASE_PATH`

Isso facilita uma futura migração para `docs.riskbands.dev` ou `riskbands.dev` sem reestruturação maior.
