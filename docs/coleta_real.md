# Coleta real — 1 de outubro de 2026

## Resultado verificado

A FACEIT Data API retornou 173 partidas de matchmaking no histórico consultado de donk666. Foram baixadas as estatísticas das 173 partidas. O recorte anunciado da Season 8 contém 160 partidas da Europe 5v5 Queue, 122 vitórias e 38 derrotas: as três contagens coincidem com a imagem fornecida pelo usuário. Não há duplicatas de match_id no recorte.

Arquivo: `data/reference/donk/season8_matches.csv`. Cada linha contém o identificador da partida, seu término UTC, kills, deaths, fila e URL oficial de origem. Respostas originais estão em `data/cache`; o histórico está em `data/reference/donk/history.json`. `verification.json` registra fontes, contagens e hashes.

São dados de um jogador, não a lista final Challenger EU. Não foi gerado boxplot comparativo.

## Período e conferências

- Data de início: 22/04/2026, segundo a [FAQ oficial do Rating](https://support.faceit.com/hc/en-us/articles/26530513602716-FACEIT-Season-8-FACEIT-Rating-FAQ).
- Horário de início: 13:00 CEST, no [anúncio de FACEIT_noon](https://www.reddit.com/r/FACEITcom/comments/1ssgpae/season_8_begins_today_at_1300_cest_make_sure_you/).
- Encerramento anunciado: 04/08/2026 às 12:59 CEST, no [anúncio de FACEIT_noon](https://www.reddit.com/r/FACEITcom/comments/1up38ge/season_8_ends_august_4_at_1259_cest/).
- Convenção do recorte: início em 22/04 às 11:00 UTC; fim exclusivo em 04/08 às 11:00 UTC, incluindo o minuto 12:59 CEST. A precisão de segundos deve ser confirmada na fonte histórica para jogos na fronteira. Nenhuma partida do donk cai nesse minuto.

Os 160 jogos somam 3.996 kills e 2.392 deaths, resultando em K/D dos totais de aproximadamente 1,67057. O painel da imagem exibe K/D 1,81; não tratamos esse valor como razão dos totais. O método acordado calcula soma de kills / soma de deaths em cada mês.

## Problemas encontrados e corrigidos

O histórico real usa status `finished` em minúsculas. O coletor anterior procurava `FINISHED` e descartaria partidas válidas. O filtro foi corrigido; os testes foram executados novamente.

A API devolveu partidas com término além do parâmetro final solicitado. Por isso, as datas são filtradas localmente a partir de `finished_at`; o filtro da API sozinho não é aceito como prova de elegibilidade.

Quatro jogos da janela ampliada pertencem à FACEIT Challenger Queue. A consulta oficial dos detalhes confirmou essa fila na região EU, mas os quatro jogos ocorreram depois do encerramento da Season 8 e ficaram fora do recorte.

A demonstração e seus gráficos foram removidos. A análise aceita apenas pacotes com dados oficiais, lista final confirmada e cobertura completa. Dados isolados de testes do programa não entram na coleta ou nos resultados.

## Impedimento para concluir o estudo

Ainda não foi obtida a lista final dos 1.000 Challenger EU da Season 8.

A página fornecida retorna 403 neste ambiente. O navegador automatizado também não inicializa por erro local do Windows (1058). A consulta pública de ranking com parâmetros `season=8`, `seasonId=8` e `season_id=8` retorna o ranking atual, igual à consulta sem temporada. Essas respostas foram rejeitadas como fonte histórica.

A documentação da Data API consultada não apresenta seleção temporal no ranking regional. O season_id=8 de uma liga mensal corresponde a maio de 2024 e também foi descartado. A busca de uma cópia arquivada da consulta de ranking em 1–5 de agosto não retornou registros.

Precisamos de uma exportação final autêntica (player_id e posição) ou de uma consulta histórica verificável da FACEIT. Rankings atuais e participantes das partidas do donk não são substitutos válidos. Não houve contato com terceiros nem envio de pedido em nome do usuário.
