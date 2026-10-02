"""Sonda limitada da Data API. Nao constitui coleta completa da Season 8."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen

from check_faceit import load_api_key, ROOT

BASE = "https://open.faceit.com/data/v4"
# Janela interna a Season 8: evita assumir o horario exato das transicoes.
START = "2026-05-01T00:00:00+00:00"
END = "2026-07-31T23:59:59+00:00"


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def stat_profile(rows):
    fields = sorted({name for row in rows for name in row})
    candidates = [name for name in fields if any(term in name.casefold() for term in ("rating", "swing", "impact"))]
    return {
        "rows": len(rows),
        "fields": fields,
        "rating_candidate_fields": candidates,
        "populated_candidate_counts": {
            name: sum(row.get(name) not in (None, "") for row in rows)
            for name in candidates
        },
    }


def run(nickname, directory):
    key = load_api_key()
    if not key:
        raise ValueError("Preencha FACEIT_API_KEY no .env.")
    directory.mkdir(parents=True, exist_ok=False)
    evidence = {
        "collected_at_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "Sonda de disponibilidade; nao e a base final nem prova de cobertura completa.",
        "nickname_requested": nickname,
        "probe_window": {"start": START, "end": END, "exact_season_boundaries": False},
        "requests": [],
    }

    def fetch(label, path, params=None, authenticated=True):
        url = BASE + path
        if params:
            url += "?" + urlencode(params)
        headers = {"Accept": "application/json"}
        if authenticated:
            headers["Authorization"] = f"Bearer {key}"
        entry = {"label": label, "url": url}
        evidence["requests"].append(entry)
        try:
            with urlopen(Request(url, headers=headers), timeout=30) as response:
                payload = json.load(response)
                entry["status"] = response.status
        except HTTPError as error:
            entry["status"] = error.code
            print(f"{label}: HTTP {error.code}")
            if error.code in (401, 403, 429):
                raise ValueError(f"Consulta interrompida: HTTP {error.code}.")
            return None
        except (URLError, OSError, ValueError) as error:
            entry["error_type"] = type(error).__name__
            print(f"{label}: falha ({type(error).__name__})")
            return None
        # Nao armazenar cabecalhos ou dados desnecessarios do perfil.
        if label == "player":
            payload = {name: payload.get(name) for name in ("player_id", "nickname", "faceit_url")}
        file = label + ".json"
        save(directory / file, payload)
        entry["file"] = file
        print(f"{label}: HTTP {entry['status']}")
        return payload

    try:
        ranking = fetch("current_ranking", "/rankings/games/cs2/regions/EU", {"limit": 3})
        evidence["current_ranking_count"] = len((ranking or {}).get("items", []))
        spec = fetch("api_spec", "/docs/swagger.json", authenticated=False)
        if spec:
            path = "/rankings/games/{game_id}/regions/{region}"
            evidence["documented_ranking_parameters"] = [
                item["name"] for item in spec["paths"][path]["get"].get("parameters", [])
            ]
            evidence["season_related_paths"] = [path for path in spec["paths"] if "season" in path]
        player = fetch("player", "/players", {"nickname": nickname})
        if not player or not player.get("player_id"):
            raise ValueError("Perfil nao localizado; confira o nickname.")
        player_id = quote(player["player_id"], safe="")
        evidence["player"] = player
        start = int(datetime.fromisoformat(START).timestamp())
        end = int(datetime.fromisoformat(END).timestamp())
        stats = fetch("player_stats_window", f"/players/{player_id}/games/cs2/stats",
                      {"from": start * 1000, "to": end * 1000, "limit": 3})
        rows = [item.get("stats", {}) for item in (stats or {}).get("items", [])]
        evidence["player_stats_profile"] = stat_profile(rows)
        evidence["player_stats_timestamps"] = [row.get("Match Finished At") for row in rows]
        history = fetch("history_window", f"/players/{player_id}/history",
                        {"game": "cs2", "from": start, "to": end, "limit": 3})
        matches = (history or {}).get("items", [])
        evidence["history_matches"] = [
            {name: match.get(name) for name in ("match_id", "started_at", "finished_at", "competition_name", "competition_type")}
            for match in matches
        ]

        # Esta numeracao de liga pode ser mensal e nao corresponder a season de CS2.
        if matches and matches[0].get("competition_id"):
            competition_id = quote(matches[0]["competition_id"], safe="")
            mm = fetch("matchmaking_details", f"/matchmakings/{competition_id}")
            if mm and mm.get("league_id"):
                league_id = quote(mm["league_id"], safe="")
                league = fetch("matchmaking_league", f"/leagues/{league_id}")
                candidate = fetch("league_season_8_candidate", f"/leagues/{league_id}/seasons/8")
                evidence["league_current_season"] = (league or {}).get("season")
                evidence["league_season_8_candidate"] = (candidate or {}).get("season")

        evidence["match_stats_profiles"] = []
        for index, match in enumerate(matches):
            match_id = quote(match["match_id"], safe="")
            payload = fetch(f"match_stats_{index + 1}", f"/matches/{match_id}/stats")
            if payload is None:
                continue
            rows = [
                player.get("player_stats", {})
                for round_data in payload.get("rounds", [])
                for team in round_data.get("teams", [])
                for player in team.get("players", [])
            ]
            profile = stat_profile(rows)
            profile["match_id"] = match["match_id"]
            evidence["match_stats_profiles"].append(profile)
    finally:
        save(directory / "summary.json", evidence)
    print(json.dumps({name: evidence.get(name) for name in (
        "player", "documented_ranking_parameters", "season_related_paths",
        "player_stats_timestamps", "history_matches", "league_season_8_candidate"
    )}, ensure_ascii=False, indent=2))
    print(f"Evidencias: {directory}")
    return evidence


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nickname", default="donk666")
    args = parser.parse_args()
    output = ROOT / "data" / "probes" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    try:
        run(args.nickname, output)
    except (ValueError, OSError) as error:
        # Mensagens controladas; nunca imprimir corpos HTTP ou credenciais.
        print("Sonda interrompida. Confira a configuracao, os arquivos locais e o status das consultas acima.")
        raise SystemExit(1)

