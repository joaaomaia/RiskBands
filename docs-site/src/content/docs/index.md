---
title: "Documentação RiskBands"
description: "Documentação oficial do RiskBands para binning com robustez temporal em risco de crédito, PD, scorecards e seleção auditável de candidatos por safra."
template: splash
hero:
  title: RiskBands
  tagline: >-
    OptimalBinning resolve muito bem o corte estático. O RiskBands aproveita
    essa força quando faz sentido e adiciona a camada que costuma faltar em
    crédito: diagnóstico temporal, penalizações estruturais, comparação entre
    candidatos e um racional mais defensável quando o portfólio muda ao longo
    do tempo.
  actions:
    - text: Começar pelo Quickstart
      link: ./technical/quickstart/
      icon: right-arrow
    - text: Ver o benchmark PD vintage
      link: ./methodology/pd-vintage-benchmark/
      icon: right-arrow
      variant: minimal
features:
  - title: Porta técnica
    description: Instalação, Quickstart, visão geral da API e exemplos para começar a usar rápido.
    link: ./technical/installation/
  - title: Porta metodológica
    description: A trilha para quem precisa entender por que binning estático sozinho nem sempre basta em risco de crédito.
    link: ./methodology/why-riskbands/
  - title: Benchmarks
    description: Benchmark PD vintage comparando OptimalBinning puro, baseline estática interna e seleção balanceada do RiskBands.
    link: ./methodology/pd-vintage-benchmark/
  - title: Exemplos
    description: Fluxos executáveis para estabilidade temporal, champion challenger e demonstrações orientadas a crédito.
    link: ./technical/examples/
  - title: API
    description: Mapa da superfície principal em torno de Binner, BinComparator, diagnósticos temporais e reporting auditável.
    link: ./technical/api-overview/
  - title: Foco em risco de crédito
    description: Pensado para PD, scorecards, safras, cobertura, bins raros, reversões e trade-offs defendíveis.
    link: ./methodology/temporal-robustness-in-credit-risk/
  - title: Publicações
    description: Espaço preparado para notas técnicas, benchmarks publicados e materiais externos do projeto.
    link: ./reference/publications/
---

## Duas portas de entrada muito claras

### Porta técnica

Use esta trilha se você já comprou a ideia e quer chegar rápido em código executável:

- [Instalação](./technical/installation/)
- [Quickstart](./technical/quickstart/)
- [Visão geral da API](./technical/api-overview/)
- [Exemplos](./technical/examples/)

### Porta metodológica

Use esta trilha se a sua pergunta principal ainda é "por que eu precisaria de algo além do binning estático?":

- [Por que RiskBands](./methodology/why-riskbands/)
- [Por que não usar apenas OptimalBinning](./methodology/why-not-only-optimal-binning/)
- [Benchmark PD vintage](./methodology/pd-vintage-benchmark/)
- [Como ler os gráficos](./methodology/how-to-read-the-charts/)
- [Robustez temporal em risco de crédito](./methodology/temporal-robustness-in-credit-risk/)

## O problema que o RiskBands tenta resolver

Em muitos fluxos de modelagem de PD, uma variável parece ótima quando olhada no agregado:

- IV forte
- KS competitivo
- cortes aparentemente limpos

Mesmo assim, a leitura por safra pode revelar um quadro bem menos confortável:

- inversões de ordenação entre bins
- perda de separação em períodos mais recentes
- bins que ficam raros ou mal cobertos
- deterioração localizada em faixas específicas do score
- racional difícil de defender em validação, comitê ou governança

É exatamente nesse ponto que o RiskBands entra.

## Onde o OptimalBinning entra de fato

O posicionamento correto do projeto não é "substituir cegamente" o `OptimalBinning`.

No repositório atual, a estratégia supervisionada numérica usa `optbinning.OptimalBinning` no backend do corte estático. Isso é importante porque reconhece um fato simples: o `OptimalBinning` já é muito bom para encontrar bons cortes estáticos.

O papel do RiskBands é outro:

- reaproveitar esse corte estático quando ele fizer sentido
- auditar o comportamento temporal do candidato
- comparar alternativas sob a mesma régua
- penalizar fragilidades estruturais
- apoiar uma decisão mais alinhada ao problema real de crédito

## Onde o RiskBands adiciona valor

O valor do projeto aparece mais claramente quando uma solução é sedutora no agregado, mas começa a levantar perguntas como:

- a ordenação continua estável entre safras?
- o event rate cruza entre bins ao longo do tempo?
- alguns bins somem, ficam raros ou perdem representatividade?
- o melhor IV agregado continua sendo a melhor resposta para crédito?
- se dois candidatos parecem plausíveis, qual deles tem o racional mais defensável?

O RiskBands adiciona essa camada por meio de:

- diagnósticos temporais por variável, bin e período
- penalizações estruturais para baixa cobertura, volatilidade e reversões
- comparação entre candidatos via `BinComparator`
- score objetivo mais próximo do trade-off real de crédito
- relatórios auditáveis para explicar por que um candidato venceu

## Mensagem central

> OptimalBinning resolve muito bem o corte estático.  
> O RiskBands ajuda a decidir se essa resposta continua sendo a resposta mais defensável quando o tempo passa a fazer parte do problema.

## Quando o estático ainda pode bastar e quando a camada temporal pesa mais

<div class="rb-grid rb-grid--2">
  <div class="rb-card rb-card--positive">
    <span class="rb-kicker">Quando o estático basta</span>
    <h3>O candidato mais simples continua competitivo</h3>
    <p>
      Em cenários mais estáveis, o RiskBands pode confirmar que a solução
      estática continua sendo a melhor resposta. Isso também é um bom resultado:
      evita trocar de candidato sem necessidade.
    </p>
  </div>
  <div class="rb-card rb-card--warn">
    <span class="rb-kicker">Quando a camada temporal importa</span>
    <h3>O agregado deixa de contar a história inteira</h3>
    <p>
      Quando surgem reversões por safra, perda de cobertura ou volatilidade de
      event rate e WoE, a decisão deixa de ser apenas “quem ganhou no IV”. É
      aí que a camada de auditoria do RiskBands começa a fazer diferença.
    </p>
  </div>
</div>

## Quando o projeto tende a ser mais útil

- variáveis de bureau ou comportamento com drift temporal
- modelos de PD e scorecards com leitura relevante por safra
- situações em que o agregado esconde fragilidade local
- estruturas com bins raros, baixa cobertura ou volatilidade alta
- contextos em que a decisão precisa sobreviver a challenge, validação e governança

## Evidência visual do benchmark

<div class="rb-callout">
  <strong>Cenário de referência:</strong> no caso <em>Temporal Reversal</em>,
  a baseline externa e a baseline estática interna preservam IV competitivo,
  mas a leitura temporal expõe fragilidade suficiente para justificar uma
  escolha diferente.
</div>

<figure class="rb-figure rb-figure--medium">
  <iframe
    src="benchmark-assets/temporal_reversal_metric_comparison.html"
    title="Benchmark PD vintage - comparacao de metricas"
    loading="lazy"
  ></iframe>
  <figcaption>
    O board comparativo mostra o ponto central da tese: a melhor leitura para
    crédito não depende apenas de IV e KS, mas também de score temporal,
    cobertura mínima e penalizações estruturais.
  </figcaption>
</figure>

<figure class="rb-figure rb-figure--tall">
  <iframe
    src="benchmark-assets/temporal_reversal_event_rate_curves.html"
    title="Benchmark PD vintage - event rate por bin ao longo do tempo"
    loading="lazy"
  ></iframe>
  <figcaption>
    Quando o event rate cruza entre bins ao longo das safras, o agregado pode
    continuar atraente enquanto a defendibilidade operacional se deteriora.
  </figcaption>
</figure>

## Por onde começar

- Quer começar por código? Vá para [Quickstart](./technical/quickstart/).
- Quer a narrativa com evidência? Vá para [Benchmark PD vintage](./methodology/pd-vintage-benchmark/).
- Quer o enquadramento conceitual? Vá para [Por que não usar apenas OptimalBinning](./methodology/why-not-only-optimal-binning/).

<div class="rb-cta-row">
  <div class="rb-cta">
    <h3>Começar a usar</h3>
    <p>Instale a biblioteca, ajuste um primeiro <code>Binner</code> e veja a API principal.</p>
    <a href="./technical/quickstart/">Ir para o Quickstart</a>
  </div>
  <div class="rb-cta">
    <h3>Comprar a tese</h3>
    <p>Entenda o benchmark PD vintage e por que a visão temporal muda decisões reais.</p>
    <a href="./methodology/pd-vintage-benchmark/">Abrir o benchmark</a>
  </div>
  <div class="rb-cta">
    <h3>Explorar exemplos</h3>
    <p>Veja scripts e notebooks para estabilidade temporal, champion challenger e benchmark.</p>
    <a href="./technical/examples/">Ver exemplos</a>
  </div>
</div>
