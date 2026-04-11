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
- `plot_event_rate_stability(pivot=None, **kwargs)`
- `save_report(path)`
- `describe_schema()`
- `get_bin_mapping(column)`

Atributos principais apos `fit`:

- `bin_summary`
- `iv_`
- `iv_by_variable_`
- `best_params_` quando `use_optuna=True`
