---
title: "Release Notes"
description: "Marcos de release em alto nível para o pacote público e para a documentação oficial."
---

## v2.0.2

Release focada em auditabilidade real, inspeção mais amigável e experiência pública mais robusta.

Principais pontos:

- nova camada pública de export com `export_binnings_json(...)`
- novo bundle auditável com `export_bundle(...)`
- `metadata_` mais forte, incluindo pesos do score e contexto efetivo do fit
- novas tabelas públicas `score_table()` e `audit_table()`
- aliases mais descobríveis para inspeção de bins
- nova camada pública de plots para bad rate, heatmap, share temporal e score components
- correção do alinhamento temporal da estratégia supervisionada, melhorando diagnostics e visualizações
- benchmark assets da documentação regenerados com charts mais largos e menos traces vazios
- docs-site reforçado para onboarding, auditoria e interpretação visual

## v2.0.1

Patch release para fechar a publicação pública com consistência:

- corrige a resolução de `riskbands.__version__` no pacote instalado fora do source tree
- adiciona teste de regressão para a leitura de versão via metadata distribuída
- preserva integralmente a renomeação para `stable`, a documentação nova e o fluxo de release da série `v2`

## v2.0.0

Release de consolidação pública:

- renomeação definitiva do valor público de `score_strategy` de `generalization_v1` para `stable`
- remoção do nome antigo da API pública, exemplos, smoke tests, labels e documentação principal
- docs-site reorganizado para onboarding, primeiros passos e navegação mais clara para novos usuários
- páginas dedicadas para `score_strategy`, `normalization_strategy`, `woe_shrinkage_strength`, Optuna e interpretação de outputs
- notebooks e exemplos alinhados ao fluxo amigável no estilo sklearn e pandas
- preparação explícita do fluxo de release para validação, GitHub Pages e publicação em PyPI via Trusted Publishing

## v1.2.0

Evolução importante da ergonomia da API pública:

- `Binner` mais alinhado a convenções de sklearn e pandas
- suporte amigável a `fit(df, y="target", column="feature")`
- `transform(...)` e `fit_transform(...)` com comportamento mais previsível para `DataFrame` e `Series`
- aliases públicos como `max_n_bins` e `monotonic_trend`
- novos métodos de inspeção: `binning_table()`, `summary()`, `report()`, `score_details()`, `diagnostics()` e `plot_stability()`
- atributos pós-fit mais fáceis de descobrir
- notebook novo com Plotly e dados sintéticos para onboarding da biblioteca

## v1.1.0

Evolução importante da camada de scoring:

- caminho legado preservado explicitamente como `legacy`
- novo objective temporal introduzido e hoje exposto publicamente como `stable`
- pesos configuráveis, normalização `absolute` e shrink de WoE
- integração consistente com `Binner`, `BinComparator`, relatórios auditáveis e Optuna
- novo exemplo mínimo comparando `legacy` versus `stable`

## v1.0.0

Mudanças estruturais importantes já refletidas no repositório:

- rename destrutivo para `riskbands`
- `Binner` estabelecido como classe principal pública
- namespace legado `nasabinning` removido
- direção de documentação orientada a benchmark estabelecida nos exemplos do repositório
