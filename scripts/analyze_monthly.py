"""Gera tabelas e boxplots mensais a partir de uma coleta verificada."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.pipeline import run_analysis

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="data/season8")
    parser.add_argument("--output", default="outputs/season8")
    parser.add_argument("--min-matches", type=int, default=1)
    parser.add_argument("--min-players", type=int, default=4)
    parser.add_argument("--highlight-id")
    args = parser.parse_args()
    try:
        monthly, stats = run_analysis(args.input, args.output, args.min_matches, args.min_players, args.highlight_id)
    except (ValueError, OSError, KeyError) as error:
        parser.exit(1, f"Análise interrompida: {error}\n")
    print(stats[["month", "analyzed_players", "player_matches", "q1", "median", "q3"]].to_string(index=False))
    print("Gráfico e tabelas salvos em:", args.output)

