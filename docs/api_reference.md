# API Reference

## `NASABinner`

Construtor principal da biblioteca.

Parametros mais usados:

- `strategy`: `"supervised"` ou `"unsupervised"` para variaveis numericas
- `max_bins`: limite padrao de bins
- `min_event_rate_diff`: fusao minima por diferenca de event rate
- `monotonic`: `"ascending"`, `"descending"` ou `None`
- `check_stability`: habilita verificacoes de estabilidade no fluxo
- `use_optuna`: ativa busca de hiperparametros para `strategy="supervised"`
- `time_col`: coluna de safra usada no diagnostico temporal
- `strategy_kwargs`: parametros especificos da estrategia

Metodos principais:

- `fit(X, y, time_col=None)`
- `transform(X, return_woe=False)`
- `fit_transform(X, y, **fit_params)`
- `stability_over_time(X, y, time_col, fill_value=None)`
- `temporal_bin_diagnostics(X, y, time_col, dataset_name=None, ...)`
- `temporal_variable_summary(X=None, y=None, diagnostics=None, time_col=None, ...)`
- `plot_event_rate_stability(pivot=None, **kwargs)`
- `save_report(path)`
- `describe_schema()`
- `get_bin_mapping(column)`

Atributos principais apos `fit`:

- `bin_summary`
- `iv_`
- `iv_by_variable_`
- `best_params_` quando `use_optuna=True`

## Camada de diagnostico temporal

`temporal_bin_diagnostics(...)` retorna um DataFrame detalhado por variavel x bin x safra, incluindo:

- `total_count`
- `event_count`
- `non_event_count`
- `bin_share`
- `event_rate`
- `woe`
- `iv_contribution`
- `coverage_flag`
- flags de rareza, cobertura, monotonicidade e reversao de ranking

`temporal_variable_summary(...)` agrega essas informacoes por variavel e expõe:

- cobertura temporal media e minima
- contagem de bins raros
- volatilidade de `event_rate`, `woe` e `bin_share`
- contagem de quebras de monotonicidade por safra
- contagem de reversoes de ranking
- `temporal_score`
- `alert_flags`
