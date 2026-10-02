"""Entrada reproduzível: grupo, partidas, período e comprovante de cobertura."""
from hashlib import sha256
import json
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

from .analysis import aggregate_monthly, classify_monthly, validate_cohort, period_bounds
from .visualization import plot_monthly


def file_hash(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def save_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def validate_config(config, cohort):
    if config.get("dataset_kind") != "official":
        raise ValueError("A análise aceita somente dados reais de fonte oficial.")
    if config.get("region") != "EU" or config.get("season") != 8:
        raise ValueError("Este projeto está configurado para Season 8 EU.")
    if config.get("final_ranking_confirmed") is not True or not config.get("cohort_source"):
        raise ValueError("Falta confirmar e documentar a fonte do ranking FINAL.")
    if not config.get("boundaries_source") or not config.get("start_utc") or not config.get("end_utc"):
        raise ValueError("Faltam limites UTC confirmados e sua fonte.")
    if not config.get("competition_ids"):
        raise ValueError("Defina as filas elegíveis em competition_ids.")
    expected = config.get("expected_players", 1000)
    if len(cohort) != expected or set(cohort["position"]) != set(range(1, expected + 1)):
        raise ValueError(f"Ranking incompleto: esperado posições 1 a {expected}.")
    period_bounds(config["start_utc"], config["end_utc"])
    return config


def load_bundle(directory):
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8-sig"))
    if manifest.get("complete") is not True:
        raise ValueError("Coleta incompleta. Não é permitido interpretar falhas como ausência de partidas.")
    for name in ("cohort.csv", "matches.csv", "coverage.csv", "config.json"):
        if file_hash(directory / name) != manifest.get("sha256", {}).get(name):
            raise ValueError(f"Arquivo alterado ou não verificado: {name}")
    cohort = validate_cohort(pd.read_csv(directory / "cohort.csv", dtype={"player_id": "string"}))
    config = json.loads((directory / "config.json").read_text(encoding="utf-8-sig"))
    validate_config(config, cohort)
    coverage = pd.read_csv(directory / "coverage.csv", dtype={"player_id": "string"})
    if coverage["player_id"].duplicated().any() or set(coverage["player_id"]) != set(cohort["player_id"]):
        raise ValueError("Cobertura não corresponde ao grupo completo.")
    if not coverage["status"].eq("complete").all():
        raise ValueError("Há jogadores com coleta incompleta.")
    matches = pd.read_csv(directory / "matches.csv", dtype={"player_id": "string", "match_id": "string"})
    if not matches["player_id"].isin(cohort["player_id"]).all():
        raise ValueError("Coleta inclui jogadores fora da lista final.")
    counts = matches.drop_duplicates(["player_id", "match_id"]).groupby("player_id").size()
    observed = coverage["player_id"].map(counts).fillna(0).astype(int)
    if not observed.eq(coverage["collected_matches"]).all() or not coverage["expected_matches"].eq(coverage["collected_matches"]).all():
        raise ValueError("Contagens de partidas não conferem com a cobertura.")
    return cohort, matches, config


def run_analysis(directory, output_dir, min_matches=1, min_players=4, highlight_id=None):
    cohort, matches, config = load_bundle(directory)
    monthly, audit = aggregate_monthly(cohort, matches, config["start_utc"], config["end_utc"], min_matches)
    if audit["outside_period_rows"]:
        raise ValueError("Pacote contém partidas fora do período configurado.")
    monthly, stats = classify_monthly(monthly, min_players)
    outliers = monthly.loc[monthly["classification"].isin(["outlier_positivo", "outlier_negativo"])]
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    monthly.to_csv(output / "player_months.csv", index=False)
    stats.to_csv(output / "monthly_statistics.csv", index=False)
    outliers.to_csv(output / "outliers.csv", index=False)
    missing = monthly.loc[monthly["status"].ne("ok")]
    missing.to_csv(output / "excluded_player_months.csv", index=False)
    fig = plot_monthly(monthly, stats, output / "monthly_kd.png",
                       title="K/D por jogador e mês",
                       period_label=f"{config['start_utc']} até {config['end_utc']} (fim exclusivo, UTC)",
                       source_label="Season 8 · Challenger EU final · FACEIT Data API · detalhes no manifesto",
                       highlight_id=highlight_id, min_matches=min_matches)
    plt.close(fig)
    save_json(output / "analysis_manifest.json", {
        "dataset_kind": config["dataset_kind"], "metric": "sum(kills) / sum(deaths)",
        "time_basis": "finished_at UTC", "interval": "[start_utc, end_utc)",
        "config": config, "min_matches": min_matches, "min_players_for_classification": min_players,
        "quartiles": "linear", "iqr_multiplier": 1.5, "audit": audit,
        "input_manifest_sha256": file_hash(Path(directory) / "manifest.json"),
        "output_sha256": {file.name: file_hash(file) for file in output.iterdir()
                          if file.name in ("player_months.csv", "monthly_statistics.csv", "outliers.csv", "excluded_player_months.csv", "monthly_kd.png")},
    })
    return monthly, stats

