---
title: "Evolução após v1.0.0"
description: "Guia amigável para entender o que mudou no RiskBands depois de v1.0.0 e como isso afeta o uso da biblioteca hoje."
---

## O que mudou desde `v1.0.0`

Depois de `v1.0.0`, o RiskBands passou por quatro movimentos importantes:

1. amadureceu a camada de score
2. deixou a API pública mais amigável
3. ganhou uma camada real de auditoria e export
4. fortaleceu a documentação e o fluxo público de release

O objetivo dessas mudanças foi simples: facilitar onboarding, governança e interpretação sem perder profundidade técnica.

## v1.1.0: objective temporal auditável

O projeto passou a expor um objective temporal mais explicável, com:

- componentes normalizados
- pesos configuráveis
- shrink de WoE
- integração consistente com `Binner`, `BinComparator` e Optuna

Hoje, essa estratégia pública aparece como `score_strategy="stable"`.

## v1.2.0: ergonomia no estilo sklearn e pandas

O `Binner` ficou mais natural para quem já usa bibliotecas maduras de Python.

Exemplos do que ficou mais fácil:

- `fit(df, y="target", column="score")`
- `transform(df)` ou `transform(df["score"])`
- `fit_transform(...)`
- `summary()`, `report()`, `score_details()` e `diagnostics()`
- `get_params()` e `set_params(...)`

## v2.0.0 a v2.0.2: consolidação pública

Nessa etapa, o foco passou a ser clareza para usuário novo e consistência de release.

Principais pontos:

- o nome público antigo `generalization_v1` saiu de cena
- `stable` passou a ser o único nome público correto para a estratégia temporal
- docs-site reorganizado com páginas de primeiros passos, score, outputs e Optuna
- exemplos e notebooks atualizados para refletir a API atual
- patch posterior para garantir que `riskbands.__version__` reflita a versão correta fora do repositório

## v2.0.2: auditoria e visualização maduras

Nesta release, o projeto ganhou uma camada mais forte para inspeção e governança:

- `export_binnings_json(...)` para gerar um JSON único e legível
- `export_bundle(...)` para produzir um pacote completo de auditoria
- `score_table()` e `audit_table()` para notebook e revisão técnica
- plots públicos para bad rate, heatmap, share temporal e score components
- metadata pós-fit com pesos do score e contexto efetivo do fit
- correção do alinhamento temporal da estratégia supervisionada

## O que usar hoje

Se você estiver chegando agora ao projeto, o caminho recomendado é:

1. instalar a biblioteca
2. seguir o [Quickstart](../technical/quickstart/)
3. usar `score_strategy="stable"` quando quiser equilíbrio entre separação e robustez temporal
4. abrir [Auditoria e plots](../technical/audit-and-plots/) e [Outputs e diagnóstico](../technical/outputs/) para aprender a ler o resultado

## O que permaneceu estável

Apesar da evolução, a direção do projeto continua a mesma:

- foco em binning, não em pipeline completo de PD
- leitura por safra e robustez temporal
- comparação auditável entre candidatos
- integração opcional com Optuna, sem acoplar o score a ele
