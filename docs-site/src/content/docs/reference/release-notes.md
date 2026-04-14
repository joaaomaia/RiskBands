---
title: "Release Notes"
description: "Marcos de release em alto nível para o pacote público e para a documentação oficial."
---

## Próximos passos

- benchmark com write-ups metodológicos mais ricos
- figuras exportadas para páginas da documentação
- referência de API mais profunda
- curadoria de publicações e notas técnicas

## Publicação inicial da documentação

Esta fase marcou a saída da documentação oficial do RiskBands para um formato
realmente navegável e publicável:

- site em Astro + Starlight
- deploy em GitHub Pages
- Home orientada a porta técnica e porta metodológica
- conteúdo principal em PT-BR
- benchmark PD vintage integrado à narrativa pública

## Consolidação da navegação

Depois da publicação inicial, a documentação também passou por uma rodada de
correção de rotas e links internos para ficar mais confiável em GitHub Pages:

- links da Home e das páginas internas alinhados ao `base` do site
- sidebar ajustada para respeitar `/RiskBands/`
- páginas de referência menos placeholder e mais honestas sobre o estado atual

## v1.0.0

Mudanças estruturais importantes já refletidas no repositório:

- rename destrutivo para `riskbands`
- `Binner` estabelecido como classe principal pública
- namespace legado `nasabinning` removido
- direção de documentação orientada a benchmark estabelecida nos exemplos do repositório

## v1.1.0

Evolução importante da camada de scoring:

- caminho legado preservado explicitamente como `legacy`
- novo objective `generalization_v1` para generalização temporal
- pesos configuráveis, normalização `absolute` e shrink de WoE
- integração consistente com `Binner`, `BinComparator`, relatórios auditáveis e Optuna
- novo exemplo mínimo comparando `legacy` versus `generalization_v1`

## Fundação da documentação

Este site em Starlight é a primeira fundação oficial da documentação pública do RiskBands:

- porta técnica
- porta metodológica
- deploy em GitHub Pages
- narrativa orientada a benchmark para usuários de risco de crédito
