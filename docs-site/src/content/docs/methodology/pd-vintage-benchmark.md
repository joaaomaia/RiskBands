---
title: "Benchmark PD vintage"
description: "Benchmark âncora que contrasta OptimalBinning puro, baseline estática interna e seleção balanceada do RiskBands em cenários com leitura por safra."
---

## Para que este benchmark existe

Esta é a página metodológica mais importante do repositório hoje.

O benchmark compara três lentes:

1. `OptimalBinning` puro como baseline externa estática
2. uma baseline estática interna do RiskBands
3. uma seleção balanceada do RiskBands que incorpora diagnóstico temporal e penalizações estruturais

Ele foi construído para perguntas de crédito, não para uma demo genérica de binning.

## Onde ele vive no repositório

- [Script do benchmark](https://github.com/joaaomaia/RiskBands/blob/master/examples/pd_vintage_benchmark/pd_vintage_benchmark.py)
- [Notebook do benchmark](https://github.com/joaaomaia/RiskBands/blob/master/examples/pd_vintage_benchmark/pd_vintage_benchmark.ipynb)
- [Guia de leitura do benchmark](https://github.com/joaaomaia/RiskBands/blob/master/examples/pd_vintage_benchmark/guia_leitura_benchmark_riskbands_ptbr.md)

## Cenários cobertos hoje

<div class="rb-grid rb-grid--3">
  <div class="rb-card rb-card--positive">
    <span class="rb-kicker">Stable Credit</span>
    <p>
      A auditoria temporal valida o candidato estático. O recado aqui é:
      sensibilidade temporal não precisa trocar vencedor quando o problema está
      sob controle.
    </p>
  </div>
  <div class="rb-card rb-card--warn">
    <span class="rb-kicker">Temporal Reversal</span>
    <p>
      O agregado continua sedutor, mas as curvas por safra revelam por que a
      resposta estática mais discriminante pode ser frágil para crédito.
    </p>
  </div>
  <div class="rb-card rb-card--neutral">
    <span class="rb-kicker">Composition Shift</span>
    <p>
      O diagnóstico temporal identifica estresse estrutural sem implicar troca
      automática do candidato final.
    </p>
  </div>
</div>

### Stable Credit

A camada temporal não precisa forçar um vencedor diferente. Este cenário existe para mostrar que o RiskBands também pode validar a solução estática quando a fragilidade temporal não é forte o suficiente para justificar uma troca.

### Temporal Reversal

É o cenário mais importante.

A história agregada continua atraente, mas a leitura por safra mostra por que a resposta estática mais discriminante pode ser a resposta errada para crédito.

### Composition Shift

Mostra que o diagnóstico temporal consegue identificar estresse estrutural sem implicar automaticamente que a escolha final precise mudar.

## O que olhar primeiro

Comece pelo board comparativo e observe:

- IV
- KS
- `temporal_score`
- `objective_score`
- `total_penalty`
- `coverage_ratio_min`
- `rare_bin_count`
- `ranking_reversal_period_count`
- `alert_flags`

Depois vá para os gráficos por safra.

## Board executivo do cenário-âncora

<figure class="rb-figure rb-figure--wide rb-figure--medium">
  <iframe
    src="../../benchmark-assets/temporal_reversal_benchmark_board.html"
    title="Benchmark board do cenário temporal reversal"
    loading="lazy"
  ></iframe>
  <figcaption>
    O board executivo concentra a comparação entre baseline externa,
    baseline estática interna e candidato final selecionado. É o ponto mais
    rápido para perceber onde IV e score temporal contam histórias diferentes.
  </figcaption>
</figure>

## O que o benchmark tenta demonstrar

Este benchmark não tenta provar que o RiskBands sempre vence a baseline estática.

Ele tenta demonstrar algo mais útil:

- às vezes o estático continua sendo a escolha certa
- às vezes a visão temporal muda a decisão
- o ganho principal está em julgar melhor o trade-off sob estresse temporal, e não apenas em trocar de solver

## Como ler o vencedor final

O ponto não é apenas observar quem teve o maior IV.

O ponto é entender por que o vencedor final:

- sustentou melhor a ordenação entre bins
- preservou cobertura mínima mais saudável
- sofreu menos com bins raros ou fragilidade estrutural
- apresentou um score objetivo mais alinhado à defendibilidade em crédito

## Onde a diferença aparece visualmente

<figure class="rb-figure rb-figure--wide rb-figure--tall">
  <iframe
    src="../../benchmark-assets/temporal_reversal_event_rate_curves.html"
    title="Curvas de event rate por abordagem no cenário temporal reversal"
    loading="lazy"
  ></iframe>
  <figcaption>
    As curvas por bin ao longo das safras mostram onde a tese do projeto fica
    concreta: o agregado continua competitivo, mas a organização temporal da
    solução estática se deteriora.
  </figcaption>
</figure>

<figure class="rb-figure rb-figure--wide rb-figure--medium">
  <iframe
    src="../../benchmark-assets/temporal_reversal_selected_heatmap.html"
    title="Heatmap do candidato selecionado no cenário temporal reversal"
    loading="lazy"
  ></iframe>
  <figcaption>
    O heatmap ajuda a localizar onde a instabilidade aparece e se ela está
    concentrada em bins ou safras específicos.
  </figcaption>
</figure>

## Limite honesto do benchmark

Este benchmark é uma prova de conceito sintética e controlada. Ele não substitui validação em base real.

Mesmo assim, ele é útil porque explicita um tipo de falha comum em crédito: o agregado parece ótimo, mas a leitura por safra conta outra história.

## Páginas relacionadas

- [Como ler os gráficos](../how-to-read-the-charts/)
- [Por que não usar apenas OptimalBinning](../why-not-only-optimal-binning/)
