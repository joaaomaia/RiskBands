# Supply chain dependencies

Contexto de hardening pre-release para a futura versao 2.0.3.

## Decisao

A dependencia runtime de `optbinning` foi limitada para `>=0.21.0,<0.22`, com constraints explicitas em:

- `ortools>=9.10.4067,<9.11`
- `protobuf>=5.29.6,<6`

Essa combinacao mantem `optbinning` em `0.21.x`, bloqueia `ortools 9.11.4210` e impede que o resolver escolha `protobuf 5.26.1`.

## Cadeia vulneravel evitada

```text
riskbands 2.0.2
  -> optbinning 0.21.0
    -> ortools 9.11.4210
      -> protobuf 5.26.1
```

`pip-audit` reportava `CVE-2025-4565` e `CVE-2026-0994` para `protobuf 5.26.1`. Nao foi usado `pip-audit --ignore-vuln`, porque a correcao e viavel por constraints de dependencias sem aceitar formalmente risco residual.

## Validacao local

Ambiente limpo Python 3.11.5 (`.venv-supply-chain`):

- `riskbands==2.0.2`
- `optbinning==0.21.0`
- `ortools==9.10.4067`
- `protobuf==5.29.6`

Checks executados com sucesso:

- `python -m pip check`
- `python -m pip_audit`
- `python -m ruff check riskbands tests`
- `python -m bandit -q -r riskbands`
- `python -m pytest -q --basetemp .pytest_tmp/supply_chain_fix --cov=riskbands --cov-report=term-missing` (`73 passed`, coverage total `79.17%`)
- `python -m build`
- `python -m twine check dist/*`
- smoke do wheel com extra `viz`, `pip check` e `pip-audit`

Python 3.12 nao estava instalado localmente; foi feita simulacao de resolver para `cp312/win_amd64`, que selecionou `optbinning-0.21.0`, `ortools-9.10.4067` e `protobuf-5.29.6`.

PyPI e TestPyPI continuam bloqueados ate a preparacao final da release. Nenhuma publicacao foi feita nesta etapa.
