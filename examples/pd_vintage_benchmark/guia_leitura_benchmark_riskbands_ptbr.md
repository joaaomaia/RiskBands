# Guia de leitura do benchmark RiskBands

## O que o notebook tenta provar

O notebook não tenta provar que o RiskBands sempre vence.

Ele tenta provar algo mais útil:

- às vezes a solução estática continua sendo a melhor;
- às vezes a leitura temporal muda a decisão;
- em crédito, olhar apenas IV agregado pode esconder fragilidade.

## Como ler o quadro-resumo inicial

O `scenario_summary` é a visão executiva.

### Colunas-chave

- `selected_candidate`: candidato final escolhido pelo benchmark.
- `selected_equals_static`: mostra se o vencedor final continuou sendo o candidato estático.
- `external_iv`, `static_iv`, `selected_iv`: comparação de IV entre as três lentes.
- `external_temporal_score`, `static_temporal_score`, `selected_temporal_score`: mostra quem ficou mais robusto no tempo.
- `external_objective_score`, `static_objective_score`, `selected_objective_score`: score final balanceado.
- `selected_advantage_vs_static`: quanto o selecionado ganhou do estático.
- `selected_advantage_vs_external`: quanto o selecionado ganhou da baseline externa.
- `selected_alert_flags`: principais alertas estruturais do vencedor final.

## Leitura dos cenários deste notebook

## 1. Stable Credit

### O que aconteceu
- O vencedor final ficou com `riskbands_static`.
- O `selected_equals_static` ficou `True`.
- O IV das três lentes ficou praticamente igual.

### Como interpretar
Esse é o cenário em que a auditoria temporal **não encontrou motivo suficiente** para abandonar a solução mais discriminante.

### Mensagem correta
O RiskBands não “falhou” aqui.
Ele fez a leitura temporal e concluiu que **não era necessário trocar**.

---

## 2. Temporal Reversal

### O que aconteceu
- A baseline externa e a baseline estática preservaram IV mais alto.
- Mesmo assim, o vencedor final foi `riskbands_temporal_quantile`.
- O `selected_equals_static` ficou `False`.
- O `selected_temporal_score` ficou acima do estático e muito acima da baseline externa.
- O `selected_objective_score` ficou claramente melhor.

### Como interpretar
Esse é o cenário mais importante do notebook.

Aqui o agregado conta uma história sedutora:
“o IV está alto, então está tudo bem”.

Mas a leitura por vintage mostra que a estrutura se deteriora.
O RiskBands aceita perder parte do IV bruto para ganhar robustez temporal.

### Mensagem correta
Esse cenário mostra por que **maximizar apenas IV pode ser insuficiente em crédito**.

---

## 3. Composition Shift

### O que aconteceu
- A baseline externa ficou mais penalizada.
- O líder temporal melhorou a leitura de estabilidade.
- Mesmo assim, o vencedor final continuou sendo `riskbands_static`.

### Como interpretar
Mudança de composição não implica troca automática.

A leitura correta é:
“o temporal ajudou a diagnosticar o problema, mas o trade-off final ainda favoreceu a solução estática interna”.

### Mensagem correta
O RiskBands não foi feito para trocar candidato toda vez que aparece drift.
Ele foi feito para **julgar melhor o trade-off**.

---

## Como ler os gráficos

## Event rate por bin ao longo do tempo
Use este gráfico para responder:
- os bins mantêm a ordenação esperada?
- há cruzamentos entre curvas?
- a distância entre bins some em certas safras?

Se houver cruzamentos frequentes, isso é um sinal de fragilidade.

## Heatmap do candidato selecionado
Use para enxergar:
- consistência do padrão por vintage
- regiões de instabilidade
- bins que parecem “sumir” ou mudar demais de comportamento

## Agregado vs vintages
Esse é um dos gráficos mais importantes.

Se o agregado parece bonito, mas a leitura por vintage revela desorganização, você encontrou exatamente o tipo de risco que o projeto quer evidenciar.

## Penalizações por abordagem
Aqui você entende por que um candidato perdeu.

Não olhe só o score final.
Olhe quais penalizações pesaram:
- bins raros
- volatilidade
- reversões
- quebra de monotonicidade
- baixa cobertura

## Distribuição do score com cortes
Esse gráfico ajuda a responder:
- os cortes parecem razoáveis?
- a variável está espremida em certas faixas?
- alguns bins ficam frágeis em determinadas regiões da distribuição?

## Regra prática para leitura final

Em crédito, uma boa leitura costuma seguir esta ordem:

1. **IV e KS** para ver separação agregada;
2. **temporal_score** para ver robustez no tempo;
3. **coverage_ratio_min**, **rare_bin_count** e **ranking_reversal_period_count** para ver fragilidade estrutural;
4. **objective_score** para ver a decisão final balanceada;
5. **winner_rationale** para justificar a escolha.

## Resumo em uma frase

- `Stable Credit`: a camada temporal valida o estático.
- `Temporal Reversal`: a camada temporal muda a decisão.
- `Composition Shift`: a camada temporal diagnostica o problema, mas não força troca.
