# Migracao de NASABinning para RiskBands

`RiskBands` e a nova identidade oficial do projeto anteriormente chamado
`NASABinning`.

## O que mudou

- o nome do projeto e da distribuicao passa a ser `riskbands`
- o repositorio passa a assumir o nome `RiskBands`
- o import principal recomendado passa a ser `riskbands`
- a classe principal recomendada para novos usos passa a ser `RiskBandsBinner`

## O que continua compativel

Durante a transicao, o namespace antigo continua funcional:

```python
import nasabinning
from nasabinning import NASABinner
from nasabinning.compare import BinComparator
```

Esse caminho antigo deve ser tratado como compatibilidade temporaria. Para novos
codigos, prefira:

```python
from riskbands import RiskBandsBinner, BinComparator
```

## Exemplo de migracao

Antes:

```python
from nasabinning import NASABinner

binner = NASABinner(check_stability=True)
```

Agora:

```python
from riskbands import RiskBandsBinner

binner = RiskBandsBinner(check_stability=True)
```

## O que nao mudou

- a tese central da biblioteca
- o foco em binning interpretavel e estabilidade temporal
- a API funcional de diagnostico, comparacao e reporting
- os ativos graficos do projeto nesta etapa

## TODO separado

Itens de identidade visual como logotipo, social preview, banner e screenshots
promocionais ficaram fora desta etapa de rename e devem ser tratados em um fluxo
proprio.
