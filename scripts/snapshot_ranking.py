"""Salva um top 500 atual verificável; nunca substitui uma captura existente."""
from datetime import datetime,timezone
from pathlib import Path
import sys
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.check_faceit import load_api_key
from src.faceit import FaceitClient
from src.pipeline import save_json,file_hash


def main():
    out=Path(__file__).resolve().parents[1]/'data/season9_top500'
    out.mkdir(parents=True,exist_ok=True)
    if (out/'ranking_manifest.json').exists():
        print('Lista fixa já existe. Captura preservada.');return
    start=datetime.now(timezone.utc).isoformat()
    attempt=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    passes=[]
    for number in [1,2]:
        client=FaceitClient(load_api_key(),out/f'ranking_raw/{attempt}/pass{number}',20)
        rows=[]
        for offset in range(0,500,100):rows.extend(client.get('/rankings/games/cs2/regions/EU',{'offset':offset,'limit':100})['items'])
        passes.append(rows)
    a,b=passes
    signature=lambda rows:[(p['position'],p['player_id'],p['faceit_elo']) for p in rows]
    if signature(a)!=signature(b):raise ValueError('Ranking mudou entre leituras; não foi fixado.')
    if len(a)!=500 or len({p['player_id'] for p in a})!=500 or {p['position'] for p in a}!=set(range(1,501)):
        raise ValueError('Ranking incompleto ou duplicado.')
    pd.DataFrame([{'player_id':p['player_id'],'player':p['nickname'],'position':p['position'],'elo_at_capture':p['faceit_elo'],'country':p.get('country','')} for p in a]).to_csv(out/'cohort.csv',index=False)
    save_json(out/'ranking_manifest.json',{'region':'EU','season':9,'ranking_kind':'current_snapshot','capture_started_utc':start,'capture_finished_utc':datetime.now(timezone.utc).isoformat(),'rows':500,'consecutive_passes_agree':True,'source':'https://open.faceit.com/data/v4/rankings/games/cs2/regions/EU','sha256':file_hash(out/'cohort.csv')})
    print('500 jogadores fixados em',start)

if __name__=='__main__':main()
