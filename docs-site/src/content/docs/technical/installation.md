---
title: "Instalação"
description: "Como instalar o RiskBands para uso da biblioteca, desenvolvimento local e manutenção da documentação."
---

## Caminho recomendado hoje

O RiskBands está estruturado primeiro como biblioteca Python. Neste momento, o caminho mais seguro é instalar a partir do código-fonte do repositório.

```bash
git clone https://github.com/joaaomaia/RiskBands.git
cd RiskBands
pip install -e .
```

Se você também pretende rodar testes, notebooks, benchmark e material de documentação:

```bash
pip install -e .[dev]
```

## O que entra na instalação principal

A instalação principal cobre as dependências necessárias para:

- binning supervisionado e não supervisionado
- diagnósticos temporais
- comparação entre candidatos
- reporting auditável
- exemplos e benchmark já presentes no repositório

## O que entra no extra de desenvolvimento

O extra `dev` adiciona dependências úteis para validação e authoring, incluindo:

- `pytest`
- `ipykernel`
- `plotly`
- `openpyxl`

Isso é especialmente útil se você quiser:

- rodar a suíte de testes
- executar os notebooks
- exportar relatórios em Excel
- visualizar o benchmark PD vintage com os gráficos atuais

## Observações práticas

- Exportação `.xlsx` exige uma engine compatível, como `openpyxl` ou `xlsxwriter`.
- O benchmark visual atual usa Plotly.
- No fluxo supervisionado numérico, o projeto depende de `optbinning`.

## Instalação da documentação

O site oficial da documentação vive em `docs-site/` e usa um toolchain separado em Node.js.

Para rodar a docs localmente:

```bash
cd docs-site
npm install
npm run dev
```

Se você estiver mexendo na documentação, veja também [Desenvolvimento](/project/development/).
