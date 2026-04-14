---
title: "Por que não usar apenas OptimalBinning"
description: "Explica com honestidade onde o OptimalBinning já é forte e onde o RiskBands adiciona a camada de decisão que falta para crédito."
---

## Comece pelo ponto honesto

O `OptimalBinning` já resolve muito bem o problema de corte estático.

O RiskBands não precisa negar isso. Pelo contrário: no repositório atual, a estratégia supervisionada numérica usa `optbinning.OptimalBinning` no backend.

Isso significa que a mensagem correta não é:

- "o RiskBands substitui completamente o OptimalBinning"

A mensagem correta é:

- "o RiskBands reaproveita um corte estático forte quando ele faz sentido e adiciona as camadas necessárias para seleção em crédito sob estresse temporal"

## O que a busca estática, sozinha, não responde

A busca estática é excelente para perguntas como:

- onde estão os melhores cortes no agregado?
- como maximizar separação estática?

Mas times de crédito também precisam responder perguntas como:

- o ordenamento entre bins sobrevive por safra?
- onde o event rate cruza ao longo do tempo?
- quais bins perdem cobertura?
- estamos aceitando um candidato com fragilidade estrutural escondida?
- se dois candidatos são plausíveis, qual deles tem o racional mais defensável?

## O que o RiskBands adiciona por cima

| Camada | Papel |
| --- | --- |
| Diagnóstico temporal | Olhar além da separação agregada |
| Penalizações estruturais | Punir bins frágeis, baixa cobertura, reversões e volatilidade |
| Comparação entre candidatos | Colocar candidatos estáticos, temporais e balanceados sob a mesma régua |
| Racional auditável | Explicar por que um candidato venceu em termos mais próximos do negócio |
| Score orientado a crédito | Balancear discriminação com defendibilidade temporal |

## Uma comparação honesta

<div class="rb-grid rb-grid--2">
  <div class="rb-card rb-card--positive">
    <span class="rb-kicker">Quando o estático continua suficiente</span>
    <p>
      Se o comportamento por safra continua coerente e a estrutura não perde
      cobertura, o RiskBands pode simplesmente confirmar o vencedor estático.
    </p>
  </div>
  <div class="rb-card rb-card--warn">
    <span class="rb-kicker">Quando a resposta estática não basta</span>
    <p>
      Se a leitura por safra revela cruzamentos, bins raros ou perda de
      coerência, maximizar apenas IV deixa de ser uma resposta confortável para
      crédito.
    </p>
  </div>
</div>

## Onde o Optuna entra, sem exagero

O projeto também pode usar `Optuna` como camada opcional de busca em fluxos supervisionados.

Esse ponto é importante, mas não deve ser confundido com a tese principal do RiskBands.

O Optuna entra para explorar configurações quando fizer sentido. O diferencial real continua sendo a régua usada para julgar os candidatos:

- separação
- estabilidade temporal
- cobertura
- reversões
- fragilidade estrutural
- score objetivo auditável

## Por que isso importa em PD

Em crédito, a decisão prática raramente é:

- "qual é o melhor conjunto de cortes estáticos do ponto de vista matemático?"

Ela costuma ser mais parecida com:

- "qual é o melhor conjunto de cortes que eu ainda consigo defender quando a carteira muda ao longo do tempo?"

É esse espaço que o RiskBands foi desenhado para ocupar.

<figure class="rb-figure rb-figure--wide rb-figure--medium">
  <iframe
    src="../../benchmark-assets/temporal_reversal_aggregate_vs_vintage.html"
    title="Agregado versus leitura por safra no benchmark"
    loading="lazy"
  ></iframe>
  <figcaption>
    Este visual ajuda a responder diretamente por que o problema não se esgota
    no corte estático: o agregado pode permanecer competitivo enquanto a visão
    por safra revela perda de coerência.
  </figcaption>
</figure>

## Páginas relacionadas

- [Por que RiskBands](../why-riskbands/)
- [Benchmark PD vintage](../pd-vintage-benchmark/)
- [Robustez temporal em risco de crédito](../temporal-robustness-in-credit-risk/)
