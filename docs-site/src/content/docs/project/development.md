---
title: "Desenvolvimento"
description: "Como manter a documentacao, validar releases e entender o deploy do site e do pacote."
---

## Biblioteca versus site da docs

O repositorio tem duas camadas de documentacao:

- `docs/` mantem material Markdown mais leve, ja existente no projeto Python
- `docs-site/` eh o site oficial em Astro + Starlight pensado para publicacao em GitHub Pages

## Fluxo local da documentacao

```bash
cd docs-site
npm install
npm run dev
```

Para gerar build de producao:

```bash
cd docs-site
npm install
npm run build
```

## Onde adicionar paginas

Crie paginas em:

`docs-site/src/content/docs/`

Regra pratica:

- use `technical/` quando a pagina ajudar alguem a instalar, rodar ou usar a API
- use `methodology/` quando a pagina ajudar alguem a entender a tese e a historia do benchmark

## Atualizando a navegacao

A navegacao principal fica em:

`docs-site/astro.config.mjs`

Se voce adicionar uma pagina e quiser deixa-la encontravel, atualize o sidebar do
Starlight ali.

## Deploy em GitHub Pages

O deploy esta configurado em:

`.github/workflows/docs-deploy.yml`

O workflow:

- roda em pushes para `master`
- instala dependencias com `npm ci` dentro de `docs-site/`
- builda o site Astro com `npm run build` dentro de `docs-site/`
- publica `docs-site/dist/` no GitHub Pages
- depende de `Settings > Pages > Source = GitHub Actions`

## Release do pacote

O repositorio tambem possui workflows separados para validacao e publicacao:

- `.github/workflows/release-validation.yml`
- `.github/workflows/publish-testpypi.yml`
- `.github/workflows/publish-pypi.yml`

Fluxo esperado:

1. atualizar versao em `pyproject.toml`
2. rodar testes, build e `twine check`
3. criar commit
4. criar tag `vX.Y.Z`
5. executar o workflow de publicacao na tag correspondente

Os workflows de publicacao validam que:

- a execucao acontece sobre uma tag
- a tag bate com a versao do `pyproject.toml`
- a distribuicao foi construida e validada antes de publicar

As publicacoes em TestPyPI e PyPI usam Trusted Publishing, sem hardcode de
token no repositorio.
