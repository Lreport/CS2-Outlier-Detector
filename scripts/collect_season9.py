"""Coleta real de um grupo fixo: histórico reconciliado com estatísticas por partida."""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.check_faceit import load_api_key
from src.faceit import FaceitClient, ApiError
from src.pipeline import file_hash, save_json
from src.analysis import validate_cohort

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/season9_top500'
CONFIG = json.loads((ROOT/'config/season9.json').read_text(encoding='utf-8'))
START = pd.Timestamp(CONFIG['start_utc'])
END = pd.Timestamp(CONFIG['end_utc'])
SCOPE = 'cs2_5v5_matchmaking_all_regions_v1'
FIELDS = ['player_id','match_id','finished_at','competition_id','region','kills','deaths','source_url']


def collect_player(client, player):
    pid = player['player_id']
    history = client.history(pid, int(START.timestamp())-86400, int(END.timestamp()))
    selected, ignored = {}, Counter()
    for match in history:
        if str(match.get('status','')).lower() != 'finished':
            ignored['unfinished'] += 1; continue
        finished = pd.Timestamp(match['finished_at'],unit='s',tz='UTC')
        if not START <= finished < END:
            ignored['outside_dates'] += 1; continue
        if match.get('competition_type') != 'matchmaking' or match.get('game_mode') != '5v5':
            ignored['outside_5v5_matchmaking'] += 1; continue
        selected[match['match_id']] = match
    raw = client.player_stats(pid, int(START.timestamp()*1000)-86400000, int(END.timestamp()*1000)) if selected else []
    by_match = defaultdict(list)
    for stats in raw:
        if stats.get('Player Id') != pid or stats.get('Game') != 'cs2':
            raise ApiError('Estatísticas retornadas para outro jogador ou jogo.')
        by_match[stats['Match Id']].append(stats)
    rows, fallback, rating_fields, missing = [], 0, set(), []
    for mid, match in selected.items():
        maps = by_match.get(mid, [])
        # Matchmaking CS2 é BO1; qualquer estrutura inesperada é conferida no endpoint da partida.
        valid = len(maps)==1 and str(maps[0].get('Best Of'))=='1'
        if valid:
            stats = maps[0]
            valid = (stats.get('Competition Id')==match['competition_id'] and
                     abs(float(stats['Match Finished At'])/1000-match['finished_at'])<=1)
        if valid:
            kills,deaths = float(stats['Kills']),float(stats['Deaths'])
            if not kills.is_integer() or not deaths.is_integer() or min(kills,deaths)<0:
                raise ApiError('Kills/deaths inválidos na API.')
            kills,deaths = int(kills),int(deaths)
            source = f'https://open.faceit.com/data/v4/players/{pid}/games/cs2/stats'
            rating_fields.update(k for k in stats if any(t in k.lower() for t in ['rating','swing']))
        else:
            fallback += 1
            source = f'https://open.faceit.com/data/v4/matches/{mid}/stats'
            try:
                kills,deaths = client.player_match(mid,pid)
            except ApiError as error:
                if str(error) not in ['Jogador ausente ou duplicado nas estatísticas da partida.', 'Partida sem estatísticas de mapas.', 'FACEIT respondeu HTTP 404; coleta interrompida.']:
                    raise
                missing.append({'player_id':pid,'match_id':mid,'finished_at':pd.Timestamp(match['finished_at'],unit='s',tz='UTC').isoformat(),
                                'reason':str(error),'source_url':source})
                continue
        rows.append(dict(player_id=pid,match_id=mid,finished_at=pd.Timestamp(match['finished_at'],unit='s',tz='UTC').isoformat(),competition_id=match['competition_id'],region=match['region'],kills=kills,deaths=deaths,source_url=source))
    return rows, {'player_id':pid,'player':player['player'],'position':player['position'],
                  'status':'complete_with_missing' if missing else 'complete','missing_matches':missing,'history_records':len(history),'expected_matches':len(selected),
                  'collected_matches':len(rows),'missing_count':len(missing),'fallback_match_queries':fallback,
                  'ignored':dict(ignored),'rating_fields':sorted(rating_fields),
                  'competition_counts':dict(Counter(r['competition_id'] for r in rows))}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--limit',type=int,default=500)
    parser.add_argument('--max-requests',type=int,default=10000)
    args=parser.parse_args()
    original=pd.read_csv(DATA/'cohort.csv',dtype={'player_id':'string'})
    cohort=validate_cohort(original)
    ranking=json.loads((DATA/'ranking_manifest.json').read_text(encoding='utf-8'))
    if file_hash(DATA/'cohort.csv')!=ranking['sha256']:raise ValueError('Lista fixa foi alterada')
    pieces=DATA/'players';pieces.mkdir(exist_ok=True)
    client=FaceitClient(load_api_key(),ROOT/'data/cache/season9',args.max_requests)
    rows,coverage=[],[]
    started=time.monotonic()
    try:
        for player in cohort.head(args.limit).to_dict('records'):
            file=pieces/(player['player_id']+'.json')
            if file.exists() and json.loads(file.read_text(encoding='utf-8')).get('collection_scope') == SCOPE:
                saved=json.loads(file.read_text(encoding='utf-8'))
                if saved.get('ranking_sha256')!=ranking['sha256']:raise ValueError('Parte pertence a outro grupo')
                player_rows,record=saved['rows'],saved['coverage']
            else:
                player_rows,record=collect_player(client,player)
                save_json(file,{'collection_scope':SCOPE,'ranking_sha256':ranking['sha256'],'retrieved_at_utc':datetime.now(timezone.utc).isoformat(),'rows':player_rows,'coverage':record})
            rows.extend(player_rows);coverage.append(record)
            if len(coverage)%10==0 or len(coverage)==1:
                print(json.dumps({'players':len(coverage),'matches':len(rows),'requests':client.requests,'elapsed_s':round(time.monotonic()-started)}),flush=True)
    finally:
        pd.DataFrame(rows,columns=FIELDS).to_csv(DATA/'matches.csv',index=False)
        flat=[{k:v for k,v in r.items() if k not in ['ignored','rating_fields','competition_counts','missing_matches']} for r in coverage]
        pd.DataFrame(flat,columns=['player_id','player','position','status','history_records','expected_matches','collected_matches','missing_count','fallback_match_queries']).to_csv(DATA/'coverage.csv',index=False)
        pd.DataFrame([m for r in coverage for m in r.get('missing_matches',[])],columns=['player_id','match_id','finished_at','reason','source_url']).to_csv(DATA/'missing_matches.csv',index=False)
        save_json(DATA/'collection_manifest.json',{'complete':len(coverage)==500,'completed_players':len(coverage),'player_match_rows':len(rows),'unique_matches':len({r['match_id'] for r in rows}),'finished_at_utc':datetime.now(timezone.utc).isoformat(),'start_utc':START.isoformat(),'end_utc':END.isoformat(),'ranking_manifest':ranking,'config':CONFIG,'coverage_details':coverage,'sha256':{n:file_hash(DATA/n) for n in ['cohort.csv','matches.csv','coverage.csv','missing_matches.csv']}})
    print('Final:',len(coverage),'jogadores;',len(rows),'participações jogador-partida.',flush=True)

if __name__=='__main__':
    main()
