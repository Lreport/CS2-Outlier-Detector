"""Distribuição semanal entre jogadores: grupo fixo, ausência e lacunas distintas."""
import numpy as np
import pandas as pd
from .analysis import prepare_matches, period_bounds, positive_integer, classify_monthly


def aggregate_weekly(cohort, matches, start, end, missing=None, min_matches=1):
    positive_integer(min_matches, 'min_matches')
    start,end=period_bounds(start,end)
    if (end-start).total_seconds() % (7*86400):
        raise ValueError('O período precisa conter semanas inteiras de sete dias.')
    cohort,data,audit=prepare_matches(cohort,matches,start,end)
    count=int((end-start).days//7)
    weeks=pd.DataFrame({'week':range(1,count+1)})
    weeks['week_start_utc']=[(start+pd.Timedelta(days=7*i)).isoformat() for i in range(count)]
    weeks['week_end_utc']=[(start+pd.Timedelta(days=7*(i+1))).isoformat() for i in range(count)]
    data['week']=((data.finished_at-start).dt.total_seconds()//(7*86400)).astype(int)+1
    grouped=data.groupby(['player_id','week'],as_index=False).agg(matches=('match_id','nunique'),kills=('kills','sum'),deaths=('deaths','sum'))
    result=cohort.merge(weeks,how='cross').merge(grouped,on=['player_id','week'],how='left',validate='one_to_one')
    for col in ['matches','kills','deaths']:result[col]=result[col].fillna(0).astype(int)
    result['missing_matches']=0
    if missing is not None and not missing.empty:
        missing=missing.copy()
        if missing.duplicated(['player_id','match_id']).any():raise ValueError('Lacuna duplicada.')
        if not missing.player_id.isin(cohort.player_id).all():raise ValueError('Lacuna fora do grupo.')
        keys=set(zip(data.player_id,data.match_id))
        if any(k in keys for k in zip(missing.player_id,missing.match_id)):raise ValueError('Partida simultaneamente coletada e ausente.')
        dates=pd.to_datetime(missing.finished_at,format='ISO8601',utc=True)
        if not dates.between(start,end,inclusive='left').all():raise ValueError('Lacuna fora do período.')
        missing['week']=((dates-start).dt.total_seconds()//(7*86400)).astype(int)+1
        counts=missing.groupby(['player_id','week']).size()
        result['missing_matches']=[int(counts.get((p,w),0)) for p,w in zip(result.player_id,result.week)]
    result['expected_matches']=result.matches+result.missing_matches
    result['status']='ok'
    result.loc[result.matches.lt(min_matches),'status']='partidas_insuficientes'
    result.loc[result.deaths.eq(0),'status']='mortes_zero'
    result.loc[result.matches.eq(0),'status']='sem_partidas'
    result.loc[result.missing_matches.gt(0),'status']='dados_incompletos'
    result['kd']=result.kills.div(result.deaths.replace(0,np.nan))
    result.loc[result.status.ne('ok'),'kd']=np.nan
    audit['missing_player_match_rows']=int(result.missing_matches.sum())
    audit['incomplete_player_weeks']=int(result.status.eq('dados_incompletos').sum())
    return result.sort_values(['week','position']).reset_index(drop=True),audit


def classify_weekly(weekly,min_players=4):
    result,stats=classify_monthly(weekly.rename(columns={'week':'month'}),min_players)
    result=result.rename(columns={'month':'week'})
    stats=stats.rename(columns={'month':'week'})
    result['percentile']=result.groupby('week')['kd'].rank(method='max',pct=True)*100
    stats['missing_player_weeks']=stats.week.map(result.status.eq('dados_incompletos').groupby(result.week).sum()).astype(int)
    stats['no_match_players']=stats.week.map(result.status.eq('sem_partidas').groupby(result.week).sum()).astype(int)
    stats['positive_outliers']=stats.week.map(result.classification.eq('outlier_positivo').groupby(result.week).sum()).astype(int)
    stats['negative_outliers']=stats.week.map(result.classification.eq('outlier_negativo').groupby(result.week).sum()).astype(int)
    return result,stats
