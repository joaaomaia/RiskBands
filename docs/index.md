# NASABinning Docs

O foco atual da biblioteca esta na consolidacao do core temporal.

Fluxo recomendado:

1. Ajustar `NASABinner(...).fit(X, y, time_col=...)`
2. Gerar bins transformados com `transform(...)`
3. Calcular o pivot temporal com `stability_over_time(...)`
4. Gerar a tabela detalhada com `temporal_bin_diagnostics(...)`
5. Gerar o sumario agregado com `temporal_variable_summary(...)`
6. Inspecionar graficamente com `plot_event_rate_stability(...)`
7. Exportar um snapshot simples com `save_report(...)`

Para detalhes da API principal, veja `docs/api_reference.md`.
