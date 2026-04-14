---
title: "Evolucao apos v1.0.0"
description: "Guia amigavel para entender o que mudou no RiskBands depois de v1.0.0 e como isso afeta o uso da biblioteca hoje."
---

## O que mudou desde `v1.0.0`

Depois de `v1.0.0`, o RiskBands passou por tres movimentos importantes:

1. amadureceu a camada de score
2. deixou a API publica mais amigavel
3. organizou melhor a documentacao e o fluxo de release

O objetivo dessas mudancas foi simples: facilitar o onboarding sem perder a
profundidade tecnica do projeto.

## v1.1.0: objective temporal auditavel

O projeto passou a expor um objective temporal mais explicavel, com:

- componentes normalizados
- pesos configuraveis
- shrink de WoE
- integracao consistente com `Binner`, `BinComparator` e Optuna

Hoje, essa estrategia publica aparece como `score_strategy="stable"`.

## v1.2.0: ergonomia no estilo sklearn e pandas

O `Binner` ficou mais natural para quem ja usa bibliotecas maduras de Python.

Exemplos do que ficou mais facil:

- `fit(df, y="target", column="score")`
- `transform(df)` ou `transform(df["score"])`
- `fit_transform(...)`
- `summary()`, `report()`, `score_details()` e `diagnostics()`
- `get_params()` e `set_params(...)`

Tambem ficaram mais claros:

- atributos pos-fit
- retorno em `DataFrame` e `Series`
- notebook de onboarding com Plotly

## v2.0.0: consolidacao publica

Nesta release, o foco passa a ser clareza para usuario novo e consistencia de
release.

Principais pontos:

- o nome publico antigo `generalization_v1` sai de cena
- `stable` passa a ser o unico nome publico correto para a estrategia temporal
- docs-site reorganizado com paginas de primeiros passos, score, outputs e Optuna
- exemplos e notebooks atualizados para refletir a API atual
- fluxo de release alinhado a tag, build validado e publicacao via Trusted Publishing

## O que usar hoje

Se voce estiver chegando agora ao projeto, o caminho recomendado eh:

1. instalar a biblioteca
2. seguir o [Quickstart](../technical/quickstart/)
3. usar `score_strategy="stable"` quando quiser equilibrio entre separacao e robustez temporal
4. abrir [Outputs e diagnostico](../technical/outputs/) para aprender a ler o resultado

## O que permaneceu estavel

Apesar da evolucao, a direcao do projeto continua a mesma:

- foco em binning, nao em pipeline completo de PD
- leitura por safra e robustez temporal
- comparacao auditavel entre candidatos
- integracao opcional com Optuna, sem acoplar o score a ele
