---
title: "Installation"
description: "How to install RiskBands from PyPI, prepare the development environment, and run the documentation locally."
---

## Recommended installation

For daily use:

```bash
pip install riskbands
```

If you also want the visual extras used in notebooks and Plotly demos:

```bash
pip install "riskbands[viz]"
```

To use the optional PySpark fit/transform paths:

```bash
pip install "riskbands[spark]"
```

The base package does not install PySpark. The `spark` extra uses
`pyspark>=3.5.2,<4`.

## Development environment

To work on the local repository, run tests, and execute notebooks:

```bash
git clone https://github.com/joaaomaia/RiskBands.git
cd RiskBands
pip install -e .[dev]
```

The `dev` extra adds useful tools for:

- tests with `pytest`
- notebooks with `ipykernel`
- `.xlsx` export
- Plotly visualizations
- release build and validation

## Main library dependencies

The main installation covers the project core:

- `pandas`
- `numpy`
- `scikit-learn`
- `optbinning`
- `optuna`
- `category_encoders`

## Practical notes

- `.xlsx` export requires a compatible engine such as `openpyxl`.
- The numeric supervised flow reuses `optbinning`.
- Optuna usage is optional.

## Local documentation

The documentation site lives in `docs-site/` and uses Astro + Starlight.

To run it locally:

```bash
cd docs-site
npm ci
npm run dev
```

To generate a production build:

```bash
cd docs-site
npm ci
npm run build
```

## After installation

The best next step is usually:

1. [Quickstart](../quickstart/)
2. [Score and strategies](../score-strategy/)
3. [Outputs and diagnostics](../outputs/)
