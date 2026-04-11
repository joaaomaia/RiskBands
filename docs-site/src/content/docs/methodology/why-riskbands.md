---
title: "Por que RiskBands"
description: "A tese central do projeto em uma página: qualidade de corte estático não basta quando a decisão precisa sobreviver ao tempo."
---

## O problema central

Em muitos fluxos de risco de crédito, uma variável é julgada principalmente pela separação agregada. Isso é útil, mas incompleto.

Um candidato de binning pode parecer forte em:

- IV agregado
- KS agregado
- cortes estáticos visualmente limpos

e ainda assim ficar difícil de defender quando você abre a análise por safra:

- comportamento do event rate por vintage
- perda de cobertura em períodos específicos
- bins raros
- reversões de ordenação
- fragilidade estrutural sob mudança de composição

## O que o RiskBands tenta resolver

O RiskBands existe para o ponto em que um time precisa responder:

> qual candidato de binning continua mais defensável quando a visão temporal entra de verdade na decisão?

É por isso que o projeto gira em torno de:

- diagnósticos temporais
- comparação entre candidatos
- penalizações estruturais
- racional auditável

## O que o projeto não está dizendo

O RiskBands não parte da premissa de que toda solução estática está errada.

Uma boa camada temporal deve, às vezes:

- confirmar o vencedor estático

e, em outros casos:

- substituir o vencedor estático por uma alternativa mais robusta

Os dois resultados podem ser corretos. O valor do projeto está em julgar melhor o trade-off, não em forçar uma escolha temporal toda vez.

## Por que isso é especialmente relevante em crédito

Trabalho de crédito é naturalmente sensível a:

- safras de originação
- mudanças de mix de concessão
- deterioração localizada
- exigências de governança e defendibilidade

Isso torna a decisão de binning mais operacional do que puramente matemática.

## A promessa prática

O RiskBands tenta ajudar a sair de uma frase como:

- "este candidato venceu no IV"

para uma frase como:

- "este candidato venceu porque continua equilibrando discriminação, estabilidade temporal, cobertura e robustez estrutural quando a carteira passa pelo tempo"

## Páginas relacionadas

- [Por que não usar apenas OptimalBinning](/methodology/why-not-only-optimal-binning/)
- [Benchmark PD vintage](/methodology/pd-vintage-benchmark/)
- [Robustez temporal em risco de crédito](/methodology/temporal-robustness-in-credit-risk/)
