# Diagnóstico de disponibilidade — FACEIT Season 8 EU

**Resultado:** conexão confirmada; coleta final ainda depende de duas fontes não obtidas: FACEIT Rating e classificação final Challenger EU.

## Escopo e evidências

Consulta executada em 1º de outubro de 2026 (UTC; noite de 30 de setembro no Brasil).
Perfil consultado: donk666, ID e5e8e2a6-d716-4493-b949-e16965f41654.
A sonda usou uma janela interna à Season 8, de 1º de maio a 31 de julho de 2026.
As três partidas retornadas terminaram em 30 e 31 de julho.
Não se tratou de uma extração completa da season ou de uma amostra representativa dos Challenger.

Arquivos originais: [pasta da sonda](../data/probes/20261001T024717084718Z/).
Verificações executáveis: [notebook de diagnóstico](../notebooks/diagnostico_api.ipynb).
Código de consulta: [sonda](../scripts/investigate_faceit.py).

## O que foi verificado

| Verificação | Evidência | Consequência |
|---|---|---|
| Autenticação | Teste de conexão e todas as 11 consultas da investigação responderam HTTP 200 | A chave e o acesso básico funcionam |
| Histórico do período | Três partidas da Europe 5v5 Queue; datas dentro da janela | É possível consultar partidas antigas; cobertura total ainda não testada |
| Correspondência entre consultas | IDs e instantes de término coincidem nas três partidas | As respostas individuais e o histórico referem-se aos mesmos eventos |
| Estatísticas de partida | 30 registros jogador-partida, 10 por partida, sem duplicata na chave partida/mapa/jogador | Amostra utilizável para inspeção de campos |
| Métricas alternativas | ADR, K/D, kills, deaths e assists presentes, numéricos e não negativos nos 30 registros | Disponíveis para eventual outro escopo, sem substituir automaticamente o rating |
| FACEIT Rating | Nenhum campo com rating, swing ou impact nos campos individuais inspecionados | Não é possível calcular a média do rating com estas respostas |
| Ranking histórico | Ranking regional documenta país, offset e limite, sem filtro temporal | O ranking atual não identifica a coorte final da Season 8 |
| Season de liga | A season 8 da liga ligada à fila EU retornou 01/05/2024 a 01/06/2024 | Trata-se de outra numeração, incompatível com a season pretendida |

O teste de autenticação fez uma consulta adicional às 11 da investigação.
Os arquivos guardam URLs e respostas públicas, sem os cabeçalhos de autenticação.

## Achados que impedem a análise pretendida

### FACEIT Rating ausente nos endpoints inspecionados
- **Severidade:** crítica para a pergunta do projeto.
- **Confiança:** alta sobre a ausência nos campos retornados; não permite generalizar para todos os serviços da FACEIT.
- **Evidência:** três estatísticas individuais e 30 registros jogador-partida de três partidas.
- **Causa:** não determinada. A métrica exibida no site pode ser fornecida por outro serviço ou por outro formato de acesso.
- **Correção:** obter endpoint suportado ou exportação do FACEIT Rating; conferir valores com o site antes da coleta.

### Coorte histórica não recuperada
- **Severidade:** crítica; usar o ranking atual mudaria a população analisada.
- **Confiança:** alta sobre os filtros documentados e as datas da liga consultada; a inexistência de outra fonte não foi demonstrada.
- **Correção:** obter classificação final oficial Challenger EU da Season 8, com IDs e posições.
- Rankings de hubs e ligas não devem ser equiparados ao ranking Challenger sem comprovar contexto e datas.

## Limitações e decisões pendentes

- As fontes oficiais indicam início da Season 8 em 22/04/2026 e da Season 9 em 05/08/2026.
  Os instantes exatos de corte UTC ainda precisam ser confirmados. A sonda evitou essas fronteiras.
- Não foi comprovada a cobertura integral do histórico nem a disponibilidade de rating para todos os jogadores.
- Não foi medida uma tendência temporal: três partidas selecionadas pelo limite de consulta não sustentam essa conclusão.
- Faltam as regras de inclusão de partidas, a regra de média do rating e o tratamento de valores ausentes.
- Não calculamos IQR nem classificamos jogadores, porque faltam a métrica e a coorte corretas.

## Próximo passo

Usar o [rascunho de solicitação à FACEIT](solicitacao_faceit.md) para pedir acesso ou exportação.
O rascunho não foi enviado. A investigação não demonstrou que a empresa exija contato;
essa é a próxima alternativa recomendada após os limites encontrados na API documentada.

## Referências oficiais

- [Data API e seus endpoints](https://docs.faceit.com/docs/data-api/data/)
- [FACEIT Rating](https://support.faceit.com/hc/en-us/articles/26530513602716-FACEIT-Season-8-FACEIT-Rating-FAQ)
- [Início da Season 8](https://support.faceit.com/hc/en-us/articles/26259323321244-FACEIT-Season-8-Placement-Matches-Soft-Reset-FAQ)
- [Início da Season 9](https://support.faceit.com/hc/en-us/articles/28898322786076-Season-9-A-Lighter-Soft-Elo-Reset-Personalised-with-your-recent-win-rate-and-FACEIT-Rating)
- [Estatísticas sazonais do perfil](https://support.faceit.com/hc/en-us/articles/28929290086556-Seasonal-Stats-FAQ)

