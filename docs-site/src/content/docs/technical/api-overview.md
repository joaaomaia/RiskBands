---
title: "Visão geral da API"
description: "Mapa da superfície principal do pacote e do fluxo orientado a crédito em torno de Binner e BinComparator."
---

## Superfície pública principal

```python
from riskbands import Binner, BinComparator
from riskbands.temporal_stability import (
    ks_over_time,
    psi_over_time,
    temporal_separability_score,
)
```

## Blocos centrais

| Componente | Papel no fluxo | Por que importa |
| --- | --- | --- |
| `Binner` | Construtor principal para binning estático e sensível ao tempo | É a porta de entrada para ajustar, transformar e auditar variáveis |
| `stability_over_time(...)` | Monta pivôs de event rate ao longo do tempo | Ajuda a enxergar rapidamente se os bins continuam coerentes por safra |
| `temporal_bin_diagnostics(...)` | Diagnóstico detalhado por variável, bin e período | Expõe cobertura, raridade, reversões e volatilidade |
| `temporal_variable_summary(...)` | Resumo temporal por variável | Facilita comparar candidatos e detectar estruturas frágeis |
| `variable_audit_report(...)` | Relatório auditável com score objetivo e racional | Transforma métricas em um artefato de decisão explicável |
| `BinComparator` | Comparação champion challenger entre múltiplas configurações | É a peça central quando o problema é escolher o candidato certo, e não apenas ajustar um |

## Fluxo orientado a crédito

### Avaliação de candidato único

Use `Binner` diretamente quando você quiser ajustar um candidato e inspecionar:

- separação estática
- estabilidade temporal
- sinais de fragilidade estrutural
- racional para reporting posterior

### Avaliação multi-candidato

Use `BinComparator` quando a tarefa real for comparar famílias de candidatos, como:

- baselines supervisionadas estáticas
- alternativas temporais ou mais conservadoras
- candidatos balanceados com guardrails mais fortes

Esse é o caminho mais natural para risco de crédito, onde a escolha final normalmente depende de trade-offs e não de uma métrica única.

## O que é tecnicamente verdadeiro no repositório atual

- o fluxo supervisionado numérico usa `optbinning.OptimalBinning` no backend do corte estático
- os diagnósticos temporais são implementados dentro do próprio RiskBands
- score objetivo e penalizações estruturais são implementados no RiskBands
- o uso de Optuna existe como camada opcional de busca em fluxos supervisionados
- o projeto já gera relatórios auditáveis e resumos de vencedor

## Onde o Optuna entra

O Optuna não é o centro da proposta do projeto.

Quando habilitado, ele funciona como uma camada opcional de busca e otimização sobre o espaço de candidatos supervisionados. O objetivo não é "otimizar por otimizar", e sim procurar configurações que conciliem:

- discriminação estática
- robustez temporal
- cobertura
- baixa fragilidade estrutural
- racional auditável

## Estratégias de score

Hoje a API expõe duas estratégias explícitas:

- `legacy`
  Mantém o score histórico orientado a maximização.
- `generalization_v1`
  Introduz um objective orientado a generalização temporal e minimização.

Exemplo:

```python
binner = Binner(
    strategy="supervised",
    check_stability=True,
    use_optuna=True,
    time_col="month",
    score_strategy="generalization_v1",
    score_weights={
        "temporal_variance_weight": 0.22,
        "window_drift_weight": 0.18,
        "rank_inversion_weight": 0.20,
        "separation_weight": 0.20,
        "entropy_weight": 0.08,
        "psi_weight": 0.12,
    },
    normalization_strategy="absolute",
    woe_shrinkage_strength=40.0,
    strategy_kwargs={"n_trials": 10},
)
```

## O que entra no `generalization_v1`

O novo objective combina:

- variância temporal ponderada do WoE shrinkado
- drift entre janelas adjacentes
- penalidade de inversão de ranking entre bins
- penalidade de separação insuficiente
- entropy penalty para estruturas degeneradas
- PSI como proxy de estabilidade em produção

Notas práticas:

- os componentes são normalizados em modo `absolute`
- o score funciona mesmo quando apenas um candidato está sendo avaliado
- o shrink de WoE é camada de robustez antes do score, não um score separado
- relatórios auditáveis expõem componentes raw, componentes normalizados, pesos e parâmetros de shrink

## Próximos passos

- [Exemplos](../examples/) para material executável
- [Por que não usar apenas OptimalBinning](../../methodology/why-not-only-optimal-binning/) para o posicionamento conceitual
- [Benchmark PD vintage](../../methodology/pd-vintage-benchmark/) para a demonstração mais forte do repositório hoje
