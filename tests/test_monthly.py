import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

import pandas as pd

from src.analysis import aggregate_monthly, classify_monthly, validate_cohort
from src.faceit import FaceitClient, ApiError
from src.collection import collect_dataset
from src.pipeline import load_bundle, file_hash, validate_config


def cohort(n=3):
    return pd.DataFrame([{"player_id": f"p{i}", "player": f"P{i}", "position": i + 1} for i in range(n)])


def match(pid="p0", mid="m0", date="2026-05-10T12:00:00Z", kills=10, deaths=10):
    return dict(player_id=pid, match_id=mid, finished_at=date, kills=kills, deaths=deaths)


class MonthlyTests(unittest.TestCase):
    def test_ratio_of_totals_not_average_ratios(self):
        games = pd.DataFrame([match(kills=10, deaths=1), match(mid="m1", kills=0, deaths=9)])
        monthly, _ = aggregate_monthly(cohort(), games, "2026-05-01Z".replace("Z", "T00:00:00Z"), "2026-06-01T00:00:00Z")
        self.assertEqual(monthly.iloc[0]["kd"], 1)
        self.assertEqual(monthly.iloc[0]["matches"], 2)

    def test_fixed_cohort_missing_month_and_zero_deaths(self):
        games = pd.DataFrame([match(), match("p1", deaths=0)])
        monthly, _ = aggregate_monthly(cohort(), games, "2026-05-01T00:00:00Z", "2026-07-01T00:00:00Z")
        self.assertEqual(len(monthly), 6)
        self.assertEqual(monthly.loc[monthly["month"].eq("2026-06"), "status"].tolist(), ["sem_partidas"] * 3)
        self.assertTrue(pd.isna(monthly.loc[monthly["status"].eq("mortes_zero"), "kd"].iloc[0]))

    def test_utc_and_exclusive_end(self):
        games = pd.DataFrame([
            match(mid="before", date="2026-04-30T23:59:59Z"),
            match(mid="first", date="2026-05-01T00:00:00Z"),
            match(mid="offset", date="2026-04-30T23:30:00-03:00"),
            match(mid="end", date="2026-06-01T00:00:00Z"),
        ])
        monthly, audit = aggregate_monthly(cohort(1), games, "2026-05-01T00:00:00Z", "2026-06-01T00:00:00Z")
        self.assertEqual(monthly.iloc[0]["matches"], 2)
        self.assertEqual(audit["outside_period_rows"], 2)

    def test_exact_duplicates_count_once_conflicts_rejected(self):
        monthly, audit = aggregate_monthly(cohort(1), pd.DataFrame([match(), match()]), "2026-05-01T00:00:00Z", "2026-06-01T00:00:00Z")
        self.assertEqual(monthly.iloc[0]["matches"], 1)
        self.assertEqual(audit["exact_duplicates_removed"], 1)
        with self.assertRaises(ValueError):
            aggregate_monthly(cohort(1), pd.DataFrame([match(), match(kills=11)]), "2026-05-01T00:00:00Z", "2026-06-01T00:00:00Z")

    def test_invalid_measurements_rejected(self):
        for value in (None, "bad", -1, 1.5, float("inf")):
            with self.subTest(value=value), self.assertRaises((ValueError, TypeError)):
                aggregate_monthly(cohort(1), pd.DataFrame([match(kills=value)]), "2026-05-01T00:00:00Z", "2026-06-01T00:00:00Z")

    def test_outside_cohort_not_in_quartiles(self):
        monthly, audit = aggregate_monthly(cohort(1), pd.DataFrame([match(), match("outsider", kills=100)]), "2026-05-01T00:00:00Z", "2026-06-01T00:00:00Z")
        self.assertEqual(len(monthly), 1)
        self.assertEqual(monthly.iloc[0]["kd"], 1)
        self.assertEqual(audit["outside_cohort_rows"], 1)

    def test_months_classified_independently_and_zero_iqr(self):
        games = [match(f"p{i}", f"a{i}", kills=(40 if i == 0 else 0 if i == 1 else 10)) for i in range(8)]
        games += [match(f"p{i}", f"b{i}", "2026-06-10T12:00:00Z", kills=40) for i in range(8)]
        monthly, _ = aggregate_monthly(cohort(8), pd.DataFrame(games), "2026-05-01T00:00:00Z", "2026-07-01T00:00:00Z")
        classified, stats = classify_monthly(monthly)
        self.assertEqual(classified.loc[classified.player_id.eq("p0"), "classification"].tolist(), ["outlier_positivo", "normal"])
        self.assertEqual(classified.loc[classified.player_id.eq("p1"), "classification"].tolist(), ["outlier_negativo", "normal"])
        self.assertTrue(stats["iqr"].eq(0).all())

    def test_value_on_fence_is_normal(self):
        values = [0, 0, 0, 1, 1, 1, 2.5]
        monthly = pd.DataFrame({"month": ["2026-05"] * 7, "kd": values, "status": ["ok"] * 7, "matches": [1] * 7})
        classified, stats = classify_monthly(monthly)
        self.assertEqual(stats.iloc[0]["upper_bound"], 2.5)
        self.assertEqual(classified.iloc[-1]["classification"], "normal")

    def test_minimum_matches_and_small_group(self):
        monthly, _ = aggregate_monthly(cohort(1), pd.DataFrame([match()]), "2026-05-01T00:00:00Z", "2026-06-01T00:00:00Z", min_matches=2)
        self.assertEqual(monthly.iloc[0]["status"], "partidas_insuficientes")
        monthly, _ = aggregate_monthly(cohort(1), pd.DataFrame([match()]), "2026-05-01T00:00:00Z", "2026-06-01T00:00:00Z")
        classified, _ = classify_monthly(monthly)
        self.assertEqual(classified.iloc[0]["classification"], "amostra_insuficiente")

    def test_duplicate_cohort_rejected(self):
        with self.assertRaises(ValueError):
            validate_cohort(pd.concat([cohort(1), cohort(1)]))


class ApiTests(unittest.TestCase):
    def test_pagination_overflow_splits_interval(self):
        with tempfile.TemporaryDirectory() as temp:
            client = FaceitClient("fake-test-key", temp)
            def page(path, params):
                if params["from"] == 0 and params["to"] == 100:
                    return {"items": [{"match_id": str(i)} for i in range(params["offset"], params["offset"] + 100)]}
                if params["from"] == 0:
                    return {"items": [{"match_id": "a"}, {"match_id": "shared"}]}
                return {"items": [{"match_id": "shared"}, {"match_id": "b"}]}
            with patch.object(client, "get", side_effect=page):
                self.assertEqual({m["match_id"] for m in client.history("p", 0, 100)}, {"a", "b", "shared"})

    def test_repeated_history_page_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            client = FaceitClient("fake-test-key", temp)
            with patch.object(client, "get", return_value={"items": [{"match_id": str(i)} for i in range(100)]}):
                with self.assertRaises(ApiError):
                    client.history("p", 0, 100)

    def test_http_error_redacted(self):
        with tempfile.TemporaryDirectory() as temp:
            client = FaceitClient("fake-test-key", temp)
            with patch("src.faceit.urlopen", side_effect=HTTPError("url", 401, "fake-test-key", {}, None)):
                with self.assertRaises(ApiError) as caught:
                    client.get("/players")
            self.assertNotIn("fake-test-key", str(caught.exception))
            self.assertEqual(list(Path(temp).iterdir()), [])

    def test_cache_reused_without_credentials(self):
        with tempfile.TemporaryDirectory() as temp:
            client = FaceitClient("fake-test-key", temp)
            with patch("src.faceit.urlopen") as opener:
                opener.return_value.__enter__.return_value = io.StringIO('{"items": []}')
                self.assertEqual(client.get("/players", {"nickname": "sample"}), {"items": []})
                self.assertEqual(client.get("/players", {"nickname": "sample"}), {"items": []})
                self.assertEqual(opener.call_count, 1)
                self.assertEqual(client.cache_hits, 1)
            self.assertNotIn("fake-test-key", next(Path(temp).glob("*.json")).read_text())

    def test_player_missing_in_stats_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            client = FaceitClient("fake-test-key", temp)
            with patch.object(client, "get", return_value={"rounds": [{"teams": [{"players": []}]}]}):
                with self.assertRaises(ApiError):
                    client.player_match("match", "player")


class BundleTests(unittest.TestCase):
    def test_non_official_dataset_rejected(self):
        with self.assertRaisesRegex(ValueError, "somente dados reais"):
            validate_config({"dataset_kind": "demo"}, cohort(1))

    def test_incomplete_collection_is_not_no_matches(self):
        config = {"dataset_kind": "official", "season": 8, "region": "EU",
                  "start_utc": "2026-05-01T00:00:00Z", "end_utc": "2026-06-01T00:00:00Z",
                  "final_ranking_confirmed": True, "cohort_source": "TEST ONLY",
                  "boundaries_source": "TEST ONLY", "expected_players": 1, "competition_ids": ["queue"]}
        with tempfile.TemporaryDirectory() as temp:
            client = FaceitClient("fake-test-key", Path(temp) / "cache")
            match_data = {"match_id": "m", "status": "finished", "competition_type": "matchmaking",
                          "competition_id": "queue", "finished_at": int(pd.Timestamp("2026-05-02T00:00:00Z").timestamp())}
            with patch.object(client, "history", return_value=[match_data]), patch.object(client, "player_match", side_effect=ApiError("failure")), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(ApiError):
                    collect_dataset(client, cohort(1), config, temp)
            manifest = json.loads((Path(temp) / "manifest.json").read_text())
            self.assertFalse(manifest["complete"])
            with self.assertRaisesRegex(ValueError, "incompleta"):
                load_bundle(temp)


if __name__ == "__main__":
    unittest.main()

