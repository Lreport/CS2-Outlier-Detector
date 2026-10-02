"""Coleta com cobertura explícita. Uma falha nunca vira mês sem partidas."""
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

from .analysis import validate_cohort, period_bounds, MATCH_COLUMNS
from .pipeline import validate_config, save_json, file_hash
from .faceit import ApiError


def collect_dataset(client, cohort, config, output_dir):
    cohort = validate_cohort(cohort)
    validate_config(config, cohort)
    start, end = period_bounds(config["start_utc"], config["end_utc"])
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    cohort.to_csv(output / "cohort.csv", index=False)
    save_json(output / "config.json", config)
    rows = []
    coverage = [{"player_id": pid, "expected_matches": 0, "collected_matches": 0,
                 "ignored_history_matches": 0, "status": "pending"} for pid in cohort["player_id"]]
    completed = False
    try:
        for index, player in enumerate(cohort.to_dict("records")):
            record = coverage[index]
            print(f"Jogador {index + 1}/{len(cohort)}: {player['player']}", flush=True)
            record["status"] = "collecting"
            # Margem de 24h para jogos que começaram antes do início e terminaram dentro.
            history = client.history(player["player_id"], int(start.timestamp()) - 86400, int(end.timestamp()))
            eligible = []
            for match in history:
                if str(match.get("status", "")).lower() != "finished":
                    continue
                if match.get("competition_type") != "matchmaking" or match.get("competition_id") not in config["competition_ids"]:
                    continue
                try:
                    finished = pd.Timestamp(match["finished_at"], unit="s", tz="UTC")
                except (KeyError, ValueError, TypeError):
                    raise ApiError("Partida finalizada sem horário válido.") from None
                if start <= finished < end:
                    eligible.append((match["match_id"], finished))
            record["ignored_history_matches"] = len(history) - len(eligible)
            record["expected_matches"] = len(eligible)
            for match_id, finished in eligible:
                kills, deaths = client.player_match(match_id, player["player_id"])
                rows.append(dict(player_id=player["player_id"], match_id=match_id,
                                 finished_at=finished.isoformat(), kills=kills, deaths=deaths))
                record["collected_matches"] += 1
            record["status"] = "complete"
        completed = True
    finally:
        for record in coverage:
            if record["status"] == "collecting":
                record["status"] = "incomplete"
        pd.DataFrame(rows, columns=MATCH_COLUMNS).to_csv(output / "matches.csv", index=False)
        pd.DataFrame(coverage).to_csv(output / "coverage.csv", index=False)
        save_json(output / "manifest.json", {
            "complete": completed, "collected_at_utc": datetime.now(timezone.utc).isoformat(),
            "source": "https://open.faceit.com/data/v4",
            "network_requests": client.requests, "cache_hits": client.cache_hits,
            "history_margin_seconds": 86400,
            "sha256": {name: file_hash(output / name) for name in ("cohort.csv", "config.json", "matches.csv", "coverage.csv")},
        })
    return coverage

