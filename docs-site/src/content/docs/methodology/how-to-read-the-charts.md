---
title: "Como ler os gráficos"
description: "Leia os visuais do benchmark na ordem certa e evite superestimar métricas agregadas."
---

## Comece pela tabela executiva

O quadro-resumo do benchmark é a melhor porta de entrada.

Use-o para responder:

- o candidato final continuou igual à baseline estática?
- a solução selecionada melhorou o `temporal_score`?
- quais penalizações ajudam a explicar a decisão final?

## IV alto não encerra a análise

Em crédito, IV alto continua sendo um sinal relevante de separação.

Mas ele não encerra a análise quando:

- a leitura por safra importa
- o portfólio sofre drift de composição
- há indícios de fragilidade estrutural

Um dos objetivos centrais do benchmark é mostrar exatamente isso: o agregado pode contar uma história otimista demais.

## Event rate por bin ao longo do tempo

Este é um dos gráficos mais importantes.

Use-o para inspecionar:

- se os bins mantêm a ordenação esperada
- se as curvas se cruzam ao longo do tempo
- se a separação encolhe nas safras mais recentes

Cruzamentos frequentes são um sinal prático de fragilidade para PD e scorecards.

<figure class="rb-figure rb-figure--tall">
  <iframe
    src="../../benchmark-assets/temporal_reversal_event_rate_curves.html"
    title="Como ler as curvas de event rate do benchmark"
    loading="lazy"
  ></iframe>
  <figcaption>
    No cenário <em>Temporal Reversal</em>, as curvas deixam claro que o
    comportamento por safra pode desmontar uma leitura excessivamente otimista
    do agregado.
  </figcaption>
</figure>

## Heatmap por bin e safra

O heatmap ajuda a enxergar:

- regiões consistentes
- regiões instáveis
- bins que mudam demais de comportamento
- safras em que a narrativa agregada deixa de combinar com a realidade local

<figure class="rb-figure rb-figure--medium">
  <iframe
    src="../../benchmark-assets/temporal_reversal_selected_heatmap.html"
    title="Como ler o heatmap de bin por safra"
    loading="lazy"
  ></iframe>
  <figcaption>
    Use o heatmap para localizar faixas ou períodos em que o comportamento muda
    demais e começa a comprometer a defendibilidade do binning.
  </figcaption>
</figure>

## Agregado versus visão por safra

Este é o ponto em que a tese do benchmark costuma ficar mais clara.

Se a visão agregada parece limpa, mas as curvas por safra parecem desorganizadas, você encontrou exatamente o tipo de desencontro que o RiskBands foi feito para expor.

<figure class="rb-figure rb-figure--medium">
  <iframe
    src="../../benchmark-assets/temporal_reversal_aggregate_vs_vintage.html"
    title="Comparacao entre agregado e leitura por safra"
    loading="lazy"
  ></iframe>
  <figcaption>
    Este visual é especialmente útil para mostrar que um agregado bonito pode
    esconder uma estrutura temporalmente frágil.
  </figcaption>
</figure>

## Penalizações e score objetivo

Não pare no score final. Olhe por que um candidato perdeu.

As penalizações costumam capturar sinais como:

- baixa cobertura
- bins raros
- volatilidade de event rate
- volatilidade de WoE
- instabilidade de share
- reversões de ordenação
- quebras de monotonicidade

Essa leitura costuma ser a mais útil em challenge, validação interna e governança.

<figure class="rb-figure rb-figure--medium">
  <iframe
    src="../../benchmark-assets/temporal_reversal_penalty_breakdown.html"
    title="Breakdown de penalizacoes do benchmark"
    loading="lazy"
  ></iframe>
  <figcaption>
    O breakdown de penalizações transforma o score final em um racional
    auditável: ele mostra exatamente onde o candidato perdeu robustez.
  </figcaption>
</figure>

## Distribuição da variável com cortes

Esse gráfico ajuda a ligar a decisão estatística à forma bruta da variável:

- os cortes estão concentrados em uma faixa estreita demais?
- as caudas ficaram finas demais?
- a estrutura final parece operacionalmente razoável quando você pensa em safras diferentes?

<figure class="rb-figure rb-figure--medium">
  <iframe
    src="../../benchmark-assets/temporal_reversal_score_distribution.html"
    title="Distribuicao do score com cortes selecionados"
    loading="lazy"
  ></iframe>
  <figcaption>
    A distribuição com cortes ajuda a conectar a decisão estatística à forma da
    variável e à viabilidade operacional da segmentação.
  </figcaption>
</figure>

## Ordem recomendada de leitura

1. comece com IV e KS para entender a separação agregada
2. depois olhe `temporal_score` para entender robustez no tempo
3. inspecione cobertura, bins raros e reversões para captar fragilidade estrutural
4. leia `objective_score` junto das penalizações
5. termine com o `rationale_summary` ou com o resumo do vencedor

## Leitura correta da troca de campeão

Quando o benchmark troca do campeão estático para outro candidato, a mensagem correta não é "o temporal sempre vence".

A mensagem correta é:

- a solução estática ficou menos defensável quando observada por safra
- o novo vencedor aceitou um trade-off melhor entre discriminação e robustez temporal
