# RiskBands

Binning orientado a **risco de crédito**, com foco em **robustez temporal**, **separabilidade**, **cobertura por safra** e **racional auditável** para seleção de cortes.

O projeto foi desenhado para responder uma pergunta muito comum em PD e scorecards:

> **um binning que parece ótimo no agregado continua defensável quando olhamos o comportamento por vintage?**

Em muitos projetos, a resposta prática é “nem sempre”. É exatamente aí que o RiskBands entra.

---

## O que é o RiskBands

RiskBands é uma biblioteca para construir, comparar e auditar candidatos de binning quando o problema real não é apenas maximizar uma métrica estática, mas também defender o resultado no tempo.

Ele foi pensado especialmente para cenários como:

- modelos de **PD**
- scorecards de crédito
- variáveis de bureau ou comportamento com **drift temporal**
- carteiras em que a leitura por safra importa
- casos em que bins raros, reversões ou perda de cobertura tornam o binning mais frágil em produção

---

## Por que não usar apenas OptimalBinning puro

O `OptimalBinning` é uma base muito forte para encontrar soluções estáticas de separação. O ponto é que, em crédito, **uma boa solução estática nem sempre é uma boa solução operacional**.

O RiskBands adiciona uma camada a mais de decisão:

- auditoria temporal por safra/vintage
- penalizações estruturais
- comparação entre candidatos
- leitura explícita de cobertura mínima, bins raros e reversões
- racional final auditável de seleção

Em outras palavras:

- **OptimalBinning puro** ajuda a encontrar um bom binning estático
- **RiskBands** ajuda a decidir se esse binning continua sendo o mais defensável para crédito ao longo do tempo

---

## O projeto usa OptimalBinning no backend

**Sim, em fluxos supervisionados o projeto usa `OptimalBinning` no backend.**

Mas isso não significa que o RiskBands seja apenas um wrapper superficial.

A diferença é que o fluxo supervisionado do projeto não para no solver estático. Ele adiciona camadas de:

- refinamento
- auditoria temporal
- penalizações
- comparação entre candidatos
- seleção explicável

Por isso, a baseline interna supervisionada do RiskBands **não é a mesma coisa** que rodar `OptimalBinning` puro de forma isolada.

---

## O projeto usa Optuna

**Sim, o projeto também contempla uso de `Optuna` em fluxos de otimização.**

A ideia aqui não é otimizar “por otimizar”, mas permitir busca mais alinhada ao problema de crédito, considerando não só separação agregada, como também:

- estabilidade temporal
- cobertura
- volatilidade de event rate e WoE
- reversões de ordenação
- objetivo balanceado e auditável

Na prática, isso abre espaço para uma busca mais coerente com a pergunta de negócio:

> **qual candidato é o melhor compromisso entre discriminação e robustez temporal?**

---

## Por que ele é mais direcionado a risco de crédito do que o OptimalBinning puro

Porque o projeto foi desenhado para lidar com problemas que são especialmente relevantes em crédito, por exemplo em modelos de **PD**:

### 1. O agregado pode enganar
Uma variável pode ter IV alto no consolidado e ainda assim perder coerência quando observada por safra.

### 2. Robustez temporal importa
Em crédito, não basta separar bem em um corte agregado. É preciso verificar se a lógica dos bins continua funcionando com mudança de composição, drift e deterioração da carteira.

### 3. Cobertura ruim machuca produção
Bins que somem, ficam raros ou perdem representatividade em certas safras podem gerar fragilidade prática.

### 4. Reversões importam
Quando a ordenação esperada entre bins se perde ao longo do tempo, o binning pode até parecer forte no treino, mas ficar mais difícil de defender em produção e governança.

### 5. A decisão final precisa ser explicável
Em vez de parar em “ganhou no IV”, o RiskBands ajuda a responder:

- por que este candidato venceu
- onde o outro perdeu
- quais penalizações pesaram
- qual foi o trade-off entre separação e estabilidade

---

## Filosofia do projeto

O RiskBands não foi desenhado para dizer que o candidato temporal sempre vence.

A proposta é mais honesta:

- quando a solução estática é suficiente, o projeto pode **validar** essa escolha
- quando a leitura por safra revela fragilidade, o projeto pode **trocar** para uma alternativa mais robusta
- quando o trade-off não compensa, o projeto pode **manter** a solução mais discriminante

Isso é especialmente útil em crédito, porque evita duas armadilhas:

- confiar demais em uma métrica agregada
- sacrificar discriminação sem necessidade

---

## Benchmark principal

O repositório já aponta para um benchmark premium comparando três lentes:

- `OptimalBinning` puro como baseline externa
- `RiskBands` estático como baseline interna
- `RiskBands` balanceado/temporal como abordagem orientada a crédito

Exemplos citados na documentação de exemplos:

- `examples/pd_vintage_benchmark/pd_vintage_benchmark.py`
- `examples/pd_vintage_benchmark/pd_vintage_benchmark.ipynb`
- `examples/pd_vintage_champion_challenger/pd_vintage_champion_challenger.py`
- `examples/temporal_stability/temporal_stability_example.py`

---

## Casos em que o projeto tende a fazer mais sentido

O RiskBands tende a agregar mais valor quando você tem:

- score ou variável contínua com comportamento diferente entre vintages
- PD com deterioração localizada em certas faixas
- overlap entre segmentos
- composição da carteira mudando ao longo do tempo
- necessidade de defender binning em comitê, validação ou governança
- preocupação com estabilidade e não apenas com performance agregada

---

## Casos em que o ganho pode ser menor

Nem todo problema exige uma camada temporal mais forte.

Se a variável já é estável ao longo das safras e a leitura agregada permanece coerente, o RiskBands pode simplesmente confirmar que o candidato estático continua sendo uma boa escolha.

Isso também é um resultado valioso.

---

## O que o projeto entrega melhor

- comparação auditável entre candidatos
- diagnóstico temporal mais explícito
- seleção orientada por trade-off
- leitura mais próxima da realidade de crédito
- benchmark mais natural para PD do que uma régua puramente estática

---

## O que o projeto não tenta ser

O foco do RiskBands é **binning**.

Ele não tenta, por si só, ser:

- pipeline completo de modelagem de PD
- framework de monitoramento de carteira
- solução completa de MLOps para crédito

A proposta é ser uma camada forte e especializada de decisão sobre binning.

---

## Como começar

Se sua pergunta principal for:

**“Por que um binning com IV alto pode ficar frágil no tempo?”**

comece por:

- `examples/pd_vintage_benchmark/pd_vintage_benchmark.ipynb`

Se você quiser primeiro entender a mecânica central da API:

- `examples/temporal_stability/temporal_stability_example.py`

Se quiser um fluxo mais direto de champion/challenger em crédito:

- `examples/pd_vintage_champion_challenger/pd_vintage_champion_challenger.ipynb`

---

## Mensagem principal

O RiskBands não tenta substituir a força do `OptimalBinning`.

Ele tenta responder melhor à pergunta que aparece no mundo real de crédito:

> **entre os candidatos que parecem bons no agregado, qual continua mais defensável quando olhamos o tempo?**
