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

## Próximos passos

- [Exemplos](/technical/examples/) para material executável
- [Por que não usar apenas OptimalBinning](/methodology/why-not-only-optimal-binning/) para o posicionamento conceitual
- [Benchmark PD vintage](/methodology/pd-vintage-benchmark/) para a demonstração mais forte do repositório hoje
