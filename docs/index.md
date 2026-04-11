# NASABinning Docs

O foco atual da biblioteca esta em consolidar binning interpretavel com estabilidade temporal, diagnostico por safra e comparacao auditavel entre candidatos.

Fluxo recomendado:

1. Ajustar `NASABinner(...).fit(X, y, time_col=...)`
2. Gerar bins transformados com `transform(...)`
3. Calcular o pivot temporal com `stability_over_time(...)`
4. Gerar a tabela detalhada com `temporal_bin_diagnostics(...)`
5. Gerar o sumario agregado com `temporal_variable_summary(...)`
6. Consolidar a escolha com `variable_audit_report(...)`
7. Inspecionar graficamente com `plot_event_rate_stability(...)`
8. Opcionalmente otimizar com `use_optuna=True` e `objective_kwargs`
9. Comparar candidatos com `BinComparator` quando houver mais de uma estrategia
10. Exportar um snapshot simples com `save_report(...)`

Para detalhes da API principal, veja `docs/api_reference.md`.

## Exemplos recomendados

- `examples/temporal_stability/temporal_stability_example.py`
  Melhor ponto de entrada para entender o fluxo base de estabilidade temporal.

- `examples/temporal_stability/temporal_stability_example.ipynb`
  Versao guiada do quickstart temporal.

- `examples/pd_vintage_champion_challenger/pd_vintage_champion_challenger.py`
  Exemplo ancora para risco de credito / PD com vintages, champion/challenger e leitura auditavel do vencedor.

- `examples/pd_vintage_champion_challenger/pd_vintage_champion_challenger.ipynb`
  Notebook didatico para mostrar por que um binning mais estavel pode vencer um challenger mais agressivo em IV.

- `examples/README.md`
  Mapa rapido para descobrir qual exemplo abrir primeiro.
