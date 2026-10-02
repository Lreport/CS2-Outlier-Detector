"""Preserva partidas reais de referência; não define nem substitui o grupo Challenger."""
import csv
from datetime import datetime, timezone
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.check_faceit import load_api_key
from src.faceit import FaceitClient
from src.pipeline import save_json, file_hash
import json

PLAYER_ID = 'e5e8e2a6-d716-4493-b949-e16965f41654'
# Janela ampla de aquisição: os cortes da season serão aplicados após confirmação.
START = '2026-04-21T00:00:00+00:00'
END = '2026-08-06T00:00:00+00:00'

def main():
    root = Path(__file__).resolve().parents[1]
    output = root / 'data/reference/donk'
    output.mkdir(parents=True, exist_ok=True)
    client = FaceitClient(load_api_key(), root / 'data/cache', max_requests=600)
    start = int(datetime.fromisoformat(START).timestamp())
    end = int(datetime.fromisoformat(END).timestamp())
    history = client.history(PLAYER_ID, start, end)
    save_json(output / 'history.json', history)
    selected = [m for m in history if str(m.get('status', '')).lower() == 'finished' and m.get('competition_type') == 'matchmaking']
    rows = []
    manifest = {
        'dataset_kind': 'official_reference', 'complete': False,
        'collected_at_utc': datetime.now(timezone.utc).isoformat(),
        'source': 'https://open.faceit.com/data/v4', 'player_id': PLAYER_ID,
        'query_start_utc': START, 'query_end_utc': END,
        'notice': 'Janela ampla de aquisição. Não é o grupo final Challenger nem a análise da Season 8. Horários de corte e lista final pendentes.',
        'history_records': len(history), 'expected_matchmaking_matches': len(selected),
    }
    save_json(output / 'manifest.json', manifest)
    print(f'Histórico: {len(history)} partidas; matchmaking concluído: {len(selected)}.', flush=True)
    try:
        for i, item in enumerate(selected, 1):
            kills, deaths = client.player_match(item['match_id'], PLAYER_ID)
            rows.append({'player_id': PLAYER_ID, 'player': 'donk666', 'match_id': item['match_id'],
                         'finished_at': datetime.fromtimestamp(item['finished_at'], timezone.utc).isoformat(),
                         'competition_id': item['competition_id'], 'kills': kills, 'deaths': deaths,
                         'source_url': 'https://open.faceit.com/data/v4/matches/' + item['match_id'] + '/stats'})
            if i % 25 == 0: print(f'Estatísticas reais verificadas: {i}/{len(selected)}', flush=True)
        manifest['complete'] = True
    finally:
        fields = ['player_id','player','match_id','finished_at','competition_id','kills','deaths','source_url']
        with (output / 'matches.csv').open('w', newline='', encoding='utf-8') as file:
            writer = csv.DictWriter(file, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        manifest.update(collected_matches=len(rows), requests=client.requests, cache_hits=client.cache_hits,
                        sha256={name:file_hash(output/name) for name in ['matches.csv','history.json']})
        save_json(output / 'manifest.json', manifest)
    config = json.loads((root / 'config/season8.json').read_text(encoding='utf-8-sig'))
    season_start = datetime.fromisoformat(config['start_utc'].replace('Z', '+00:00'))
    season_end = datetime.fromisoformat(config['end_utc'].replace('Z', '+00:00'))
    season_rows = [row for row in rows if season_start <= datetime.fromisoformat(row['finished_at']) < season_end
                   and row['competition_id'] in config['competition_ids']]
    with (output / 'season8_matches.csv').open('w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(season_rows)
    season_ids = {row['match_id'] for row in season_rows}
    wins = 0
    for match in history:
        if match['match_id'] not in season_ids:
            continue
        factions = [name for name, team in match['teams'].items()
                    if any(player['player_id'] == PLAYER_ID for player in team['players'])]
        if len(factions) != 1:
            raise ValueError('Jogador ausente ou duplicado nas equipes do histórico.')
        wins += match['results']['winner'] == factions[0]
    kills = sum(row['kills'] for row in season_rows)
    deaths = sum(row['deaths'] for row in season_rows)
    save_json(output / 'verification.json', {
        'scope': 'Somente donk; não representa a lista final Challenger EU.',
        'config': config, 'matches': len(season_rows), 'wins': wins, 'losses': len(season_rows)-wins,
        'kills': kills, 'deaths': deaths, 'kd_ratio_of_totals': kills/deaths if deaths else None,
        'duplicate_match_ids': len(season_rows)-len(season_ids),
        'screenshot_reference': {'matches':160,'wins':122,'losses':38},
        'screenshot_counts_match': [len(season_rows),wins,len(season_rows)-wins] == [160,122,38],
        'boundary_minute_matches': [r['match_id'] for r in rows
                                   if abs((datetime.fromisoformat(r['finished_at'])-season_end).total_seconds()) <= 60],
        'history_returned_outside_query_window': sum(not (start <= m['finished_at'] <= end) for m in selected),
        'query_note': 'A API retornou partidas além do limite solicitado. O recorte é aplicado localmente pelo finished_at.',
        'sha256': {name:file_hash(output/name) for name in ['history.json','matches.csv','season8_matches.csv']},
    })
    print(f'Coleta de referência: {len(rows)} partidas reais; recorte Season 8: {len(season_rows)} jogos, {wins} vitórias. Nenhum boxplot gerado.', flush=True)

if __name__ == '__main__':
    main()
