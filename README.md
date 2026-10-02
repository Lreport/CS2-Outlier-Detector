# CS2 Outlier Detector

Análise real do K/D semanal de um grupo fixo dos **top 500 FACEIT EU**, com destaque para donk666. A lista foi capturada em **01/10/2026**; o período observado vai de **05/08 a 29/09/2026**, em oito blocos de sete dias UTC.

## Resultado e arquivos

- [Gráfico para slides](outputs/season9_weekly/boxplot_semanal.png), também disponível em SVG e PDF na mesma pasta.
- [Relatório com resultados, método e limitações](outputs/season9_weekly/relatorio.md).
- [Notebook executado](notebooks/analise_semanal_top500.ipynb).
- [Resultado do donk por semana](outputs/season9_weekly/donk_weekly.csv).
- [Todos os jogadores por semana](outputs/season9_weekly/player_weeks.csv).
- [Outliers](outputs/season9_weekly/outliers.csv) e [recorrência por jogador](outputs/season9_weekly/outlier_recurrence.csv).

Donk é outlier superior nas semanas 6 e 7, entre sete semanas com valor elegível. A semana 4 tem uma estatística ausente na API e não recebeu K/D calculado com dados parciais. O resultado da semana 6 usa cinco partidas; o da semana 7 usa 29.

A coleta percorreu os 500 jogadores. Foram preservadas 83.340 participações jogador-partida com estatísticas e 33 lacunas explícitas. Participações não equivalem a partidas distintas: uma mesma partida pode conter vários jogadores do grupo. A verificação dirigida de 56 participações no endpoint individual concordou com os valores coletados.

## Método

1. Fixar os 500 jogadores e posições do ranking atual EU, com duas leituras consecutivas idênticas.
2. Coletar partidas concluídas de matchmaking CS2 5v5 desses jogadores. EU define o grupo; partidas em outras regiões também entram. Hubs e torneios ficam fora.
3. Agrupar pelo término registrado no histórico, em dias UTC: 05–11/08, 12–18/08, 19–25/08, 26/08–01/09, 02–08/09, 09–15/09, 16–22/09 e 23–29/09.
4. Calcular **K/D = soma de kills / soma de deaths**, um valor por jogador-semana. Cada jogador tem peso igual nos quartis.
5. Calcular Q1 e Q3 com interpolação linear e limites de 1,5 × IQR separadamente em cada semana.

Sem partidas ou com zero deaths, o K/D fica ausente. Se uma partida esperada não tem estatística válida, o jogador-semana inteiro é excluído da caixa e identificado como incompleto. O mínimo principal é uma partida; o relatório inclui sensibilidade para mínimos de cinco e dez.

O grupo é o top 500 **na coleta**, não o top 500 de cada semana nem o ranking final de setembro. O FACEIT Rating não apareceu nos campos consultados; K/D é a alternativa autorizada. Elo só seleciona o grupo. Outlier é uma descrição da distribuição, não um teste de significância.

O recorte usa oito semanas de calendário UTC a partir da data de lançamento. Meia-noite em 05/08 é uma convenção do estudo; não foi confirmada como o horário exato da abertura da temporada. Essa limitação deve acompanhar a interpretação da primeira semana.

## Reproduzir no Windows

O ambiente `.venv` já contém Pandas, Matplotlib, Jupyter e as dependências utilizadas. A chave permanece somente em `.env`, variável `FACEIT_API_KEY`; esse arquivo não deve ser publicado.

```powershell
# A captura existente é preservada; não atualiza silenciosamente o grupo.
.\.venv\Scripts\python.exe scripts/snapshot_ranking.py

# Retoma partes salvas e reaproveita respostas originais em cache.
.\.venv\Scripts\python.exe scripts/collect_season9.py

# Conferência, análise e notebook, nessa ordem.
.\.venv\Scripts\python.exe scripts/verify_season9.py
.\.venv\Scripts\python.exe scripts/analyze_weekly.py
.\.venv\Scripts\python.exe scripts/build_notebook.py

# Abrir o notebook.
.\.venv\Scripts\python.exe -m notebook notebooks/analise_semanal_top500.ipynb
```

A configuração do recorte está em `config/season9.json`. A análise exige a coleta dos 500 históricos e a reconciliação das contagens; consultas incompletas não geram o resultado final. Falhas de rede interrompem a execução sem eliminar o progresso salvo.

## Proveniência

- `data/season9_top500/cohort.csv`: lista fixa, posição e Elo na captura.
- `ranking_manifest.json`: horário e integridade da captura.
- `matches.csv`: valores reais e URLs de origem; `missing_matches.csv`: lacunas e razões.
- `coverage.csv` e `collection_manifest.json`: reconciliação de cada jogador.
- `verification.json`: checagens independentes por partida e filas observadas.
- `data/cache/season9`: respostas originais da API, sem credenciais.
- `outputs/season9_weekly/analysis_manifest.json`: método e integridade dos resultados.

O cache e as partes intermediárias ficam preservados localmente e fora do Git por volume. Para transferir a investigação completa, inclua esses diretórios separadamente; para reproduzir os resultados publicados, os CSVs, manifestos e código são suficientes.

## Testes e ambiente

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Para recriar o ambiente: Python 3.12, `python -m venv .venv` e `.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt`.

## Histórico da Season 8

A investigação anterior foi preservada em `docs/coleta_real.md` e `data/reference/donk`. Ela contém partidas reais do donk, mas não a lista final Challenger EU. O estudo ativo passou a ser o top 500 atual da Season 9. Os antigos scripts mensais não são a entrada do fluxo atual. Não existem dados de demonstração nos resultados.
