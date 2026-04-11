# RiskBands Docs

Este e o ponto de entrada da documentacao do projeto.

## Fluxo recomendado

1. Ajustar `RiskBandsBinner(...).fit(X, y, time_col=...)`
2. Transformar os dados com `transform(...)`
3. Gerar o pivot temporal com `stability_over_time(...)`
4. Abrir a tabela detalhada com `temporal_bin_diagnostics(...)`
5. Resumir a estabilidade com `temporal_variable_summary(...)`
6. Consolidar o racional com `variable_audit_report(...)`
7. Comparar candidatos com `BinComparator`, quando houver champion/challenger

## Navegacao rapida

- [README.md](../README.md)
  Visao geral do projeto, instalacao, quickstart e posicionamento.

- [docs/api_reference.md](api_reference.md)
  Contrato principal da API e superficie publica do pacote.

- [docs/migration.md](migration.md)
  Nota de migracao do rename de `NASABinning` para `RiskBands`.

- [examples/README.md](../examples/README.md)
  Mapa dos exemplos principais.

- [examples/temporal_stability/temporal_stability_example.py](../examples/temporal_stability/temporal_stability_example.py)
  Quickstart temporal minimo.

- [examples/pd_vintage_champion_challenger/pd_vintage_champion_challenger.py](../examples/pd_vintage_champion_challenger/pd_vintage_champion_challenger.py)
  Exemplo ancora de risco de credito / PD com vintages.

## O que procurar em credito

As pecas mais relevantes para um fluxo de PD e scorecards interpretaveis sao:

- `temporal_separability_score(...)`
- `temporal_bin_diagnostics(...)`
- `temporal_variable_summary(...)`
- `variable_audit_report(...)`
- `BinComparator` com `candidate_profile_summary()` e `winner_summary()`

## Validacao

Validacao rapida local:

```bash
pytest -q --basetemp .pytest_tmp
```

Workflow leve de CI:

- [tests.yml](../.github/workflows/tests.yml)
