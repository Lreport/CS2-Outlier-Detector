"""Conferências independentes de integridade e amostra no endpoint por partida."""
from pathlib import Path
import sys
import json
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.analyze_weekly import load_verified,DATA,ROOT,DONK
from scripts.check_faceit import load_api_key
from src.faceit import FaceitClient
from src.pipeline import save_json,file_hash
from src.weekly import aggregate_weekly


def main():
    cohort,matches,missing,coverage,manifest=load_verified()
    weekly,audit=aggregate_weekly(cohort,matches,manifest['start_utc'],manifest['end_utc'],missing)
    dates=pd.to_datetime(matches.finished_at,utc=True)
    selected=[]
    # Primeira e última partida para posições espaçadas pela lista fixa.
    for pid in cohort.iloc[::31].player_id:
        group=matches.loc[matches.player_id.eq(pid)].sort_values('finished_at')
        if len(group):selected.extend([group.iloc[0],group.iloc[-1]])
    # Duas partidas por semana elegível do donk, quando disponíveis.
    donk=matches.loc[matches.player_id.eq(DONK)].copy()
    donk['week']=((pd.to_datetime(donk.finished_at,utc=True)-pd.Timestamp(manifest['start_utc'])).dt.days//7)+1
    for _,group in donk.groupby('week'):
        group=group.sort_values('finished_at');selected.extend([group.iloc[0],group.iloc[-1]])
    # Inclui o jogador-semana com maior K/D em cada semana para verificar extremos.
    for _,group in weekly.loc[weekly.kd.notna()].groupby('week'):
        record=group.loc[group.kd.idxmax()]
        candidates=matches.loc[matches.player_id.eq(record.player_id) & dates.ge(pd.Timestamp(record.week_start_utc)) & dates.lt(pd.Timestamp(record.week_end_utc))]
        selected.append(candidates.sort_values('kills',ascending=False).iloc[0])
    checks=pd.DataFrame(selected).drop_duplicates(['player_id','match_id'])
    client=FaceitClient(load_api_key(),ROOT/'data/cache/season9',200)
    results=[]
    for row in checks.to_dict('records'):
        k,d=client.player_match(row['match_id'],row['player_id'])
        agrees=(k==row['kills'] and d==row['deaths'])
        results.append({'player_id':row['player_id'],'match_id':row['match_id'],'kills':k,'deaths':d,'agrees':bool(agrees)})
        if not agrees:raise ValueError('Divergência no endpoint individual: '+row['match_id'])
    if int(weekly.matches.sum())!=len(matches):raise ValueError('Agregação perdeu partidas')
    if int(weekly.kills.sum())!=int(matches.kills.sum()) or int(weekly.deaths.sum())!=int(matches.deaths.sum()):raise ValueError('Totais divergentes')
    queues=[]
    for q in sorted(matches.competition_id.unique()):
        data=client.get('/matchmakings/'+q)
        if data.get('game')!='cs2':raise ValueError('Fila fora do recorte')
        save_json(DATA/('queue_'+q+'.json'),data)
        queues.append({'id':q,'name':data['name'],'region':data['region'],'player_match_rows':int(matches.competition_id.eq(q).sum())})
    save_json(DATA/'verification.json',{'all_checks_pass':True,'sample_size':len(results),'sampling':'Posições espaçadas na lista; extremos temporais por jogador; duas partidas por semana do donk; maior K/D semanal. Não é amostragem probabilística.','individual_match_checks':results,'aggregation_totals_match':True,'queues':queues,'audit':audit,'collection_manifest_sha256':file_hash(DATA/'collection_manifest.json')})
    print('Verificação concluída:',len(results),'registros conferidos no endpoint individual; somas e filas corretas.')

if __name__=='__main__':main()
