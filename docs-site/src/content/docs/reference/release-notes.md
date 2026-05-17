---
title: "Release Notes"
description: "Marcos de release em alto nível para o pacote público e para a documentação oficial."
---

## v2.2.0

Compatible minor release focused on auditable missing-value policy and compatibility.

Main points:

- `missing_policy="standard"` is the default and preserves the Sprint A baseline behavior
- `missing_policy="separate_bin"` is opt-in and creates explicit `Missing` bins, including categorical missing values
- `missing_policy="forbid"` raises during `fit` or `transform` when selected features contain missing values
- `standard` is the canonical name for the historical maximize-oriented score strategy
- `legacy` remains accepted as a compatibility alias for `standard`
- pandas and PySpark inputs are supported by the missing-policy contract
- bundles persist `missing_policy`, `effective_missing_policy`, `missing_profile`, and `missing_decision_log`
- old bundles without these fields continue to load as `standard`
- PySpark remains optional through `riskbands[spark]` with `pyspark>=3.5,<4`

Notes:

- merge policies such as `merge_nearest_woe` and `merge_nearest_event_rate` are not part of this target
- no opaque intelligent imputation is added
- a full distributed Spark fitting backend is not part of this target

## v2.1.0

Compatible minor release focused on the preferred `RiskBands` name, optional PySpark paths, and validation profiles.

Main points:

- `RiskBands` is the preferred public estimator name; `Binner` remains compatible
- `min_n_bins` records a soft quality status without forcing artificial cuts
- `sample_size` controls PySpark fit sampling
- pandas/PySpark inputs are detected automatically in `fit` and `transform`
- pandas outputs remain pandas; PySpark outputs remain PySpark
- `fit(validate=True)` and `transform(validate=True)` create validation profiles with separate fit and transform reports
- v2.1.0 bundles persist schema/version metadata, profiles, separate validation reports, sampling/backend metadata, and data schema when available
- PySpark remains optional through `riskbands[spark]` with `pyspark>=3.5,<4`

Notes:

- PySpark fit uses controlled sampling plus the current pandas engine
- PySpark transform and validation profiles use native Spark expressions and aggregated profiles
- A full distributed Spark fitting backend is not part of this release

## v2.0.3

Patch release focused on release hardening and deterministic operational behaviour.

Main points:

- stronger categorical handling for rare categories, missing values, and unknown categories
- safer `export_bundle(...)` outputs with sanitized names and a traceable manifest
- explicit `force_numeric` support
- stronger quality gates with `ruff`, coverage-enabled `pytest`, `pip check`, `bandit`, and `pip-audit`
- supply-chain constraints to avoid the vulnerable `ortools 9.11.4210 -> protobuf 5.26.1` resolver path
- README and release governance updates for pandas, Spark/Databricks usage, overrides, auditable export, assets, and local prompts

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
