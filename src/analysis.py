"""Coorte fixa, K/D mensal e limites de Tukey (1,5 x IQR)."""
import numpy as np
import pandas as pd

MATCH_COLUMNS = ["player_id", "match_id", "finished_at", "kills", "deaths"]


def positive_integer(value, name, minimum=1):
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{name} deve ser inteiro >= {minimum}.")
    return value


def validate_cohort(cohort):
    required = ["player_id", "player", "position"]
    if not set(required).issubset(cohort.columns) or cohort.empty:
        raise ValueError("Ranking vazio ou sem player_id, player e position.")
    result = cohort[required].copy()
    for column in ("player_id", "player"):
        result[column] = result[column].astype("string").str.strip()
        if result[column].isna().any() or result[column].eq("").any():
            raise ValueError(f"Ranking contém {column} ausente.")
    positions = pd.to_numeric(result["position"], errors="coerce")
    if not np.isfinite(positions).all() or positions.lt(1).any() or positions.mod(1).ne(0).any():
        raise ValueError("Posições devem ser inteiros positivos.")
    result["position"] = positions.astype(int)
    if result["player_id"].duplicated().any() or result["position"].duplicated().any():
        raise ValueError("Ranking contém ID ou posição duplicada.")
    return result.sort_values("position").reset_index(drop=True)


def period_bounds(start, end):
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    if start.tzinfo is None or end.tzinfo is None or start >= end:
        raise ValueError("Informe início e fim com fuso horário e início anterior ao fim.")
    return start.tz_convert("UTC"), end.tz_convert("UTC")


def prepare_matches(cohort, matches, start, end):
    """Valida, remove duplicatas exatas e aplica coorte e período UTC."""
    cohort = validate_cohort(cohort)
    start, end = period_bounds(start, end)
    if not set(MATCH_COLUMNS).issubset(matches.columns):
        raise ValueError("Partidas precisam de: " + ", ".join(MATCH_COLUMNS))
    data = matches[MATCH_COLUMNS].copy()
    for column in ("player_id", "match_id"):
        data[column] = data[column].astype("string").str.strip()
        if data[column].isna().any() or data[column].eq("").any():
            raise ValueError(f"Partida com {column} ausente.")
    for column in ("kills", "deaths"):
        values = pd.to_numeric(data[column], errors="coerce")
        if not np.isfinite(values).all() or values.lt(0).any() or values.mod(1).ne(0).any():
            raise ValueError(f"{column} deve conter inteiros não negativos, sem ausências.")
        data[column] = values.astype("int64")
    date_text = data["finished_at"].astype("string")
    if not date_text.str.contains(r"(?:Z|[+-]\d{2}:?\d{2})$", case=False, na=False).all():
        raise ValueError("finished_at precisa explicitar UTC ou o fuso horário.")
    data["finished_at"] = pd.to_datetime(date_text, format="ISO8601", utc=True, errors="raise")
    original = len(data)
    data = data.drop_duplicates()
    removed = original - len(data)
    if data.duplicated(["player_id", "match_id"]).any():
        raise ValueError("Registros conflitantes para o mesmo jogador e partida.")
    outsider = ~data["player_id"].isin(cohort["player_id"])
    outside_period = ~data["finished_at"].between(start, end, inclusive="left")
    audit = {
        "input_rows": original,
        "exact_duplicates_removed": removed,
        "outside_cohort_rows": int(outsider.sum()),
        "outside_period_rows": int(outside_period.sum()),
    }
    data = data.loc[~outsider & ~outside_period].copy()
    audit["eligible_player_match_rows"] = len(data)
    return cohort, data, audit


def aggregate_monthly(cohort, matches, start, end, min_matches=1):
    """Usa término UTC e intervalo [início, fim). Ausência não vira K/D zero."""
    positive_integer(min_matches, "min_matches")
    start, end = period_bounds(start, end)
    cohort, data, audit = prepare_matches(cohort, matches, start, end)
    data["month"] = data["finished_at"].dt.strftime("%Y-%m")
    months = pd.period_range(start.tz_localize(None).to_period("M"),
                             (end - pd.Timedelta(nanoseconds=1)).tz_localize(None).to_period("M"), freq="M").astype(str)
    grid = cohort.merge(pd.DataFrame({"month": months}), how="cross")
    grouped = data.groupby(["player_id", "month"], as_index=False).agg(
        matches=("match_id", "nunique"), kills=("kills", "sum"), deaths=("deaths", "sum"))
    monthly = grid.merge(grouped, on=["player_id", "month"], how="left", validate="one_to_one")
    for column in ("matches", "kills", "deaths"):
        monthly[column] = monthly[column].fillna(0).astype(int)
    monthly["status"] = "ok"
    monthly.loc[monthly["matches"].lt(min_matches), "status"] = "partidas_insuficientes"
    monthly.loc[monthly["deaths"].eq(0), "status"] = "mortes_zero"
    monthly.loc[monthly["matches"].eq(0), "status"] = "sem_partidas"
    monthly["kd"] = monthly["kills"].div(monthly["deaths"].replace(0, np.nan))
    monthly.loc[monthly["status"].ne("ok"), "kd"] = np.nan
    return monthly.sort_values(["month", "position"]).reset_index(drop=True), audit


def classify_monthly(monthly, min_players=4):
    """Quartis lineares; < min_players: apenas descrição, sem classificação."""
    positive_integer(min_players, "min_players", 2)
    result = monthly.copy()
    result["classification"] = result["status"]
    summaries = []
    for month, group in result.groupby("month", sort=True):
        valid = group["kd"].notna()
        values = group.loc[valid, "kd"]
        row = {
            "month": month, "cohort_players": len(group),
            "active_players": int(group["matches"].gt(0).sum()),
            "analyzed_players": len(values),
            "player_matches": int(group["matches"].sum()),
            "q1": np.nan, "median": np.nan, "q3": np.nan, "iqr": np.nan,
            "lower_bound": np.nan, "upper_bound": np.nan,
            "classification_enabled": len(values) >= min_players,
        }
        if len(values):
            q1, median, q3 = values.quantile([.25, .5, .75], interpolation="linear")
            iqr = q3 - q1
            row.update(q1=float(q1), median=float(median), q3=float(q3), iqr=float(iqr),
                       lower_bound=float(q1 - 1.5 * iqr), upper_bound=float(q3 + 1.5 * iqr))
            idx = group.index[valid]
            result.loc[idx, "classification"] = "normal" if row["classification_enabled"] else "amostra_insuficiente"
            if row["classification_enabled"]:
                result.loc[group.index[valid & group["kd"].lt(row["lower_bound"])], "classification"] = "outlier_negativo"
                result.loc[group.index[valid & group["kd"].gt(row["upper_bound"])], "classification"] = "outlier_positivo"
        summaries.append(row)
    return result, pd.DataFrame(summaries)

