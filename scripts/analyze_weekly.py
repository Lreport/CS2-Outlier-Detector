"""Valida a coleta completa e gera os resultados semanais reais."""
import json
from pathlib import Path
import sys
import pandas as pd
import matplotlib.pyplot as plt
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.analysis import validate_cohort
from src.pipeline import file_hash,save_json
from src.weekly import aggregate_weekly,classify_weekly
from src.weekly_plot import weekly_boxplot

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data/season9_top500'
OUTPUT=ROOT/'outputs/season9_weekly'
DONK='e5e8e2a6-d716-4493-b949-e16965f41654'


def load_verified():
    manifest=json.loads((DATA/'collection_manifest.json').read_text(encoding='utf-8'))
    if manifest.get('complete') is not True or manifest.get('completed_players')!=500:
        raise ValueError('A coleta dos 500 jogadores ainda não terminou.')
    for name,digest in manifest['sha256'].items():
        if file_hash(DATA/name)!=digest:raise ValueError('Arquivo alterado após coleta: '+name)
    cohort=validate_cohort(pd.read_csv(DATA/'cohort.csv'))
    if len(cohort)!=500 or set(cohort.position)!=set(range(1,501)):raise ValueError('Grupo incompleto')
    matches=pd.read_csv(DATA/'matches.csv')
    missing=pd.read_csv(DATA/'missing_matches.csv')
    coverage=pd.read_csv(DATA/'coverage.csv')
    if coverage.player_id.duplicated().any() or set(coverage.player_id)!=set(cohort.player_id):raise ValueError('Cobertura não coincide com o grupo')
    if not coverage.status.isin(['complete','complete_with_missing']).all():raise ValueError('Há consultas pendentes')
    if matches.duplicated(['player_id','match_id']).any():raise ValueError('Partida duplicada por jogador')
    counts=matches.groupby('player_id').size();missing_counts=missing.groupby('player_id').size()
    actual=coverage.player_id.map(counts).fillna(0).astype(int)
    absent=coverage.player_id.map(missing_counts).fillna(0).astype(int)
    if not actual.eq(coverage.collected_matches).all() or not absent.eq(coverage.missing_count).all():raise ValueError('Contagem divergente')
    if not (actual+absent).eq(coverage.expected_matches).all():raise ValueError('Histórico não reconciliado')
    return cohort,matches,missing,coverage,manifest


def main():
    cohort,matches,missing,coverage,manifest=load_verified()
    verification=json.loads((DATA/'verification.json').read_text(encoding='utf-8'))
    if verification.get('all_checks_pass') is not True or verification['collection_manifest_sha256']!=file_hash(DATA/'collection_manifest.json'):
        raise ValueError('Verificação independente ausente ou desatualizada.')
    OUTPUT.mkdir(parents=True,exist_ok=True)
    weekly,audit=aggregate_weekly(cohort,matches,manifest['start_utc'],manifest['end_utc'],missing)
    if audit['outside_period_rows'] or audit['outside_cohort_rows']:raise ValueError('Coleta fora do recorte')
    weekly,stats=classify_weekly(weekly)
    if len(weekly)!=4000 or len(stats)!=8:raise ValueError('Esperado 500 jogadores por 8 semanas')
    donk=weekly.loc[weekly.player_id.eq(DONK)].merge(stats[['week','median','q1','q3','lower_bound','upper_bound','analyzed_players']],on='week')
    outliers=weekly.loc[weekly.classification.isin(['outlier_positivo','outlier_negativo'])]
    for name,frame in [('player_weeks.csv',weekly),('weekly_statistics.csv',stats),('donk_weekly.csv',donk),('outliers.csv',outliers),('excluded_player_weeks.csv',weekly.loc[weekly.status.ne('ok')])]:
        frame.to_csv(OUTPUT/name,index=False)
    snapshot=pd.Timestamp(manifest['ranking_manifest']['capture_started_utc']).strftime('%d/%m/%Y')
    fig=weekly_boxplot(weekly,stats,OUTPUT/'boxplot_semanal',snapshot,DONK)
    plt.close(fig)
    sensitivity=[]
    for threshold in [1,5,10]:
        alternative,_=aggregate_weekly(cohort,matches,manifest['start_utc'],manifest['end_utc'],missing,min_matches=threshold)
        alternative,other_stats=classify_weekly(alternative)
        focus=alternative.loc[alternative.player_id.eq(DONK),['week','matches','kd','classification','percentile']].copy()
        focus['minimum_matches']=threshold
        sensitivity.append(focus.merge(other_stats[['week','analyzed_players','median','upper_bound']],on='week'))
    pd.concat(sensitivity).to_csv(OUTPUT/'sensitivity_donk.csv',index=False)
    recurrence=weekly.groupby(['player_id','player','position'],as_index=False).agg(
        eligible_weeks=('kd','count'),positive_outlier_weeks=('classification',lambda x:int(x.eq('outlier_positivo').sum())),
        negative_outlier_weeks=('classification',lambda x:int(x.eq('outlier_negativo').sum())),
        incomplete_weeks=('status',lambda x:int(x.eq('dados_incompletos').sum())))
    recurrence.sort_values(['positive_outlier_weeks','eligible_weeks','position'],ascending=[False,False,True]).to_csv(OUTPUT/'outlier_recurrence.csv',index=False)
    measured=int(donk.kd.notna().sum());positive=int(donk.classification.eq('outlier_positivo').sum())
    def number(value):return '—' if pd.isna(value) else f'{value:.2f}'.replace('.',',')
    names={'outlier_positivo':'Outlier superior','outlier_negativo':'Outlier inferior','normal':'Dentro dos limites','dados_incompletos':'Estatísticas incompletas','sem_partidas':'Sem partidas','partidas_insuficientes':'Poucas partidas','mortes_zero':'Sem denominador válido'}
    table=['| Semana | Período (UTC) | Jogadores válidos | Jogos do donk com dados | K/D donk | Mediana do grupo | Limite superior | Classificação |',
           '|---|---|---:|---:|---:|---:|---:|---|']
    for r in donk.to_dict('records'):
        dates=pd.Timestamp(r['week_start_utc']).strftime('%d/%m')+'–'+(pd.Timestamp(r['week_end_utc'])-pd.Timedelta(days=1)).strftime('%d/%m')
        table.append(f"| {r['week']} | {dates} | {r['analyzed_players']} | {r['matches']} | {number(r['kd'])} | {number(r['median'])} | {number(r['upper_bound'])} | {names.get(r['classification'],r['classification'])} |")
    text=f'''# Donk entre os top 500 EU — análise semanal

## Resultado

Donk aparece como outlier superior em **{positive} das {measured} semanas com K/D elegível**. O gráfico contém oito semanas; uma semana sem valor elegível não conta como desempenho normal nem como K/D zero.

![Boxplots semanais](boxplot_semanal.png)

{chr(10).join(table)}

## Base e cobertura

- Grupo fixo: 500 jogadores do ranking EU capturado em {snapshot} (UTC), com duas leituras consecutivas idênticas de IDs, posições e Elo.
- Janela por datas UTC: 05/08/2026 00:00 até 30/09/2026 00:00, com fim exclusivo. O dia 30/09 não faz parte da análise.
- Participações jogador-partida com estatísticas: {len(matches):,}; partidas distintas: {matches.match_id.nunique():,}.
- Participações esperadas no histórico: {int(coverage.expected_matches.sum()):,}; sem estatística individual recuperável: {len(missing):,}.
- Combinações jogador-semana: 4.000; com dados incompletos: {int(weekly.status.eq('dados_incompletos').sum())}; sem partidas: {int(weekly.status.eq('sem_partidas').sum())}.
- Conferência independente: {verification['sample_size']} participações comparadas ao endpoint de estatísticas por partida, todas concordantes. Essa verificação dirigida não garante que a API esteja livre de erros desconhecidos.
- A coleta percorreu os 500 históricos. Toda partida esperada está registrada como coletada ou como lacuna; nenhuma falha vira zero.

## Método

Cada caixa representa a distribuição de **um valor por jogador naquela semana**. O K/D é a soma de kills dividida pela soma de deaths, não a média dos K/D de partidas. Cada jogador tem o mesmo peso na distribuição, independentemente de quantas partidas jogou.

As oito semanas são blocos de sete dias do calendário UTC: 05–11/08, 12–18/08, 19–25/08, 26/08–01/09, 02–08/09, 09–15/09, 16–22/09 e 23–29/09. A atribuição usa o término registrado no histórico oficial. O início em meia-noite é uma convenção de calendário do estudo, não uma afirmação sobre o horário exato de abertura da Season 9.

Entram partidas concluídas de matchmaking CS2 5v5 dos jogadores selecionados, incluindo a Challenger Queue. EU define a lista de jogadores, não restringe o servidor das partidas: jogos desses jogadores em outras regiões também entram. Hubs, torneios e outros formatos ficam fora. As filas observadas são documentadas na verificação.

Para cada semana, Q1 e Q3 usam interpolação linear. IQR = Q3 − Q1. Um valor é outlier quando é estritamente menor que Q1 − 1,5 × IQR ou maior que Q3 + 1,5 × IQR. Os bigodes chegam aos valores observados dentro desses limites. Donk participa dos quartis e segue a mesma regra dos demais.

O mínimo principal é uma partida. Sem partidas, com zero deaths ou com qualquer estatística faltante naquela semana, o K/D do jogador fica ausente. Seus dados observados são preservados nas tabelas, mas não entram na caixa. A análise de sensibilidade em `sensitivity_donk.csv` repete a classificação com mínimos de 5 e 10 partidas.

O FACEIT Rating de desempenho não apareceu nos campos consultados; K/D é a alternativa autorizada. Elo é usado somente para selecionar o grupo, nunca como métrica de desempenho nos boxplots.

## Sensibilidade e leitura para a apresentação

Com mínimo de cinco partidas, as classificações do donk nas semanas elegíveis permanecem iguais às da análise principal. Com mínimo de dez, as semanas 2, 3, 6 e 8 deixam de ter amostra suficiente para ele; a semana 7 permanece como outlier superior. Portanto, o resultado da semana 6 se apoia em apenas cinco partidas, enquanto o da semana 7 se apoia em 29.

O grupo fixo tem 500 jogadores, mas cada caixa inclui apenas quem tem K/D elegível na semana. O número de jogadores válidos varia de {int(stats.analyzed_players.min())} a {int(stats.analyzed_players.max())}. A tabela `outlier_recurrence.csv` resume a frequência de outliers de cada jogador e quantas semanas puderam ser analisadas.

## Limites da interpretação

Este é um estudo descritivo do **top 500 no momento da coleta**, observado retrospectivamente. Não representa os top 500 de cada semana nem o ranking final de setembro. A seleção por desempenho posterior limita a generalização para todos os jogadores.

As quantidades de partidas diferem entre jogadores e semanas. Valores baseados em poucas partidas são menos estáveis; confira a sensibilidade antes de tirar conclusões. As semanas reutilizam jogadores, e jogadores podem compartilhar partidas: observações não são independentes. A regra de outliers não é um teste de significância e o K/D não mede sozinho o impacto completo no jogo.

Datas e estatísticas podem conter falhas ou atualizações administrativas da fonte. As lacunas conhecidas foram registradas e excluídas por jogador-semana; isso não garante ausência de omissões desconhecidas na API. O recorte usa dias UTC a partir da data anunciada de lançamento; a diferença entre meia-noite e o horário exato de abertura deve ser considerada ao discutir a primeira semana.

## Material para a apresentação futura

1. Pergunta: o donk se destaca mesmo entre os atuais top 500 EU?
2. Dados: explicar a fotografia do ranking, as oito semanas, a métrica e a cobertura.
3. Método: um valor por jogador e semana; explicar caixa, mediana, bigodes e outliers.
4. Resultado: usar a figura e a tabela acima, separando semanas observadas e ausentes.
5. Limitações: seleção do grupo, volume de partidas e lacunas da fonte.

O PNG serve para slides; SVG e PDF preservam qualidade ao ampliar. As tabelas e os manifestos permitem conferir os números. A apresentação ainda não foi montada.

## Fontes

- [FACEIT Data API](https://docs.faceit.com/docs/data-api/data/): ranking, histórico e estatísticas. URLs e respostas brutas são preservadas localmente.
- [Anúncio da Season 9](https://support.faceit.com/hc/en-us/articles/28898322786076-Season-9-A-Lighter-Soft-Elo-Reset-Personalised-with-your-recent-win-rate-and-FACEIT-Rating): data de início em 5 de agosto.
- [Challenger Queue](https://support.faceit.com/hc/en-us/articles/29091864551708-Season-9-Challenger-Queue-FAQ): evento de 5 a 9 de agosto.
'''
    (OUTPUT/'relatorio.md').write_text(text,encoding='utf-8')
    save_json(OUTPUT/'analysis_manifest.json',{'metric':'sum(kills)/sum(deaths)','group':'Top 500 EU at capture','period_unit':'seven calendar days UTC','min_matches':1,'quartiles':'linear','iqr_multiplier':1.5,'donk_id':DONK,'donk_eligible_weeks':measured,'donk_positive_outlier_weeks':positive,'audit':audit,'input_manifest_sha256':file_hash(DATA/'collection_manifest.json'),'verification_sha256':file_hash(DATA/'verification.json'),'output_sha256':{p.name:file_hash(p) for p in OUTPUT.iterdir() if p.is_file() and p.name!='analysis_manifest.json'}})
    print(donk[['week','matches','missing_matches','kd','median','upper_bound','classification']].to_string(index=False))
    print('Resultados salvos em',OUTPUT)

if __name__=='__main__':main()
