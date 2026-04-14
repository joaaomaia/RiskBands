---
title: "Instalação"
description: "Como instalar o RiskBands a partir do PyPI, preparar o ambiente de desenvolvimento e rodar a documentação localmente."
---

## Instalação recomendada

Para usar a biblioteca no dia a dia:

```bash
pip install riskbands
```

Se você também quiser os extras visuais usados em notebooks e demos com Plotly:

```bash
pip install "riskbands[viz]"
```

## Ambiente de desenvolvimento

Para trabalhar no repositório local, rodar testes e executar notebooks:

```bash
git clone https://github.com/joaaomaia/RiskBands.git
cd RiskBands
pip install -e .[dev]
```

O extra `dev` adiciona ferramentas úteis para:

- testes com `pytest`
- notebooks com `ipykernel`
- exportação `.xlsx`
- visualizações com Plotly
- build e validação de release

## Dependências principais da biblioteca

A instalação principal cobre o núcleo do projeto:

- `pandas`
- `numpy`
- `scikit-learn`
- `optbinning`
- `optuna`
- `category_encoders`

## Observações práticas

- Exportação `.xlsx` exige uma engine compatível, como `openpyxl`.
- O fluxo supervisionado numérico reaproveita `optbinning`.
- O uso de Optuna é opcional.

## Documentação local

O site da documentação vive em `docs-site/` e usa Astro + Starlight.

Para rodar localmente:

```bash
cd docs-site
npm ci
npm run dev
```

Para gerar build de produção:

```bash
cd docs-site
npm ci
npm run build
```

## Depois da instalação

O melhor próximo passo costuma ser:

1. [Quickstart](../quickstart/)
2. [Score e estratégias](../score-strategy/)
3. [Outputs e diagnóstico](../outputs/)
