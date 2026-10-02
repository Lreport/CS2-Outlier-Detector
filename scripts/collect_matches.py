"""Coleta K/D das partidas do ranking FINAL confirmado, com cache para retomada."""
import argparse
import json
from pathlib import Path
import sys
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.analysis import validate_cohort
from src.pipeline import validate_config
from src.faceit import FaceitClient, ApiError
from src.collection import collect_dataset
from check_faceit import load_api_key

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort", default="data/final_ranking.csv")
    parser.add_argument("--config", default="config/season8.json")
    parser.add_argument("--output", default="data/season8")
    parser.add_argument("--cache", default="data/cache")
    parser.add_argument("--max-requests", type=int, default=200)
    args = parser.parse_args()
    try:
        if args.max_requests < 1:
            raise ValueError("max-requests deve ser positivo.")
        config = json.loads(Path(args.config).read_text(encoding="utf-8-sig"))
        cohort = validate_cohort(pd.read_csv(args.cohort, dtype={"player_id": "string"}))
        validate_config(config, cohort)
        client = FaceitClient(load_api_key(), args.cache, args.max_requests)
        collect_dataset(client, cohort, config, args.output)
    except (ApiError, ValueError, OSError, KeyError) as error:
        # Não imprime exceções de terceiros com credenciais ou corpos HTTP.
        print(str(error) if isinstance(error, ApiError) else "Configuração ou entrada inválida. Confira ranking final, período e caminhos.")
        raise SystemExit(1)
    print("Coleta completa. Arquivos salvos em:", args.output)

