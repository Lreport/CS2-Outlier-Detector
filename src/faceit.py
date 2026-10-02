"""Cliente limitado à Data API oficial, com cache e paginação verificável."""
from hashlib import sha256
import json
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen

BASE = "https://open.faceit.com/data/v4"


class ApiError(RuntimeError):
    pass


class FaceitClient:
    def __init__(self, key, cache_dir, max_requests=200):
        if not key:
            raise ApiError("Chave FACEIT ausente.")
        self.key = key
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_requests = max_requests
        self.requests = 0
        self.cache_hits = 0

    def get(self, path, params=None):
        # Nunca aceita URL externa: credencial só vai para a origem oficial.
        if not path.startswith("/") or "://" in path or path.startswith("//"):
            raise ApiError("Caminho de API inválido.")
        url = BASE + path + ("?" + urlencode(sorted(params.items())) if params else "")
        file = self.cache_dir / (sha256(url.encode()).hexdigest() + ".json")
        if file.exists():
            cached = json.loads(file.read_text(encoding="utf-8"))
            if cached.get("url") != url:
                raise ApiError("Cache inconsistente.")
            self.cache_hits += 1
            return cached["data"]
        if self.requests >= self.max_requests:
            raise ApiError("Limite de consultas desta execução atingido; repita para continuar pelo cache.")
        self.requests += 1
        if self.requests > 1:
            time.sleep(.15)
        try:
            request = Request(url, headers={"Authorization": f"Bearer {self.key}", "Accept": "application/json"})
            with urlopen(request, timeout=30) as response:
                data = json.load(response)
        except HTTPError as error:
            raise ApiError(f"FACEIT respondeu HTTP {error.code}; coleta interrompida.") from None
        except (URLError, OSError, ValueError):
            raise ApiError("Falha de conexão ou resposta inválida; coleta interrompida.") from None
        tmp = file.with_suffix(".tmp")
        tmp.write_text(json.dumps({"url": url, "data": data}, ensure_ascii=False), encoding="utf-8")
        tmp.replace(file)
        return data

    def history(self, player_id, start_second, end_second):
        """Intervalo inclusivo da API. Divide janelas que excedam offset=1000."""
        def window(lo, hi):
            items, seen = [], set()
            for offset in range(0, 1001, 100):
                payload = self.get(f"/players/{quote(player_id, safe='')}/history",
                                   {"game": "cs2", "from": lo, "to": hi, "offset": offset, "limit": 100})
                page = payload.get("items")
                if not isinstance(page, list):
                    raise ApiError("Histórico sem lista de partidas.")
                ids = [item.get("match_id") for item in page]
                if any(not item for item in ids):
                    raise ApiError("Histórico com partida sem identificador.")
                if len(page) and set(ids).issubset(seen):
                    raise ApiError("Paginação repetiu a mesma página; cobertura não confirmada.")
                seen.update(ids)
                items.extend(page)
                if len(page) < 100:
                    return items
            if hi - lo <= 1:
                raise ApiError("Volume excede paginação mesmo na menor janela.")
            middle = (lo + hi) // 2
            return window(lo, middle) + window(middle, hi)
        # Mesma partida pode aparecer nas duas metades inclusivas.
        found = {}
        for item in window(start_second, end_second):
            match_id = item["match_id"]
            if match_id in found and found[match_id] != item:
                raise ApiError("Histórico retornou dados conflitantes para a mesma partida.")
            found[match_id] = item
        return list(found.values())

    def player_match(self, match_id, player_id):
        payload = self.get(f"/matches/{quote(match_id, safe='')}/stats")
        kills, deaths, maps, seen = 0, 0, 0, {}
        for index, map_data in enumerate(payload.get("rounds", [])):
            map_key = map_data.get("match_round", index)
            if map_data.get("match_id") not in (None, match_id):
                raise ApiError("Estatísticas pertencem a outra partida.")
            players = [player for team in map_data.get("teams", []) for player in team.get("players", [])
                       if player.get("player_id") == player_id]
            if len(players) != 1:
                raise ApiError("Jogador ausente ou duplicado nas estatísticas da partida.")
            stats = players[0].get("player_stats", {})
            try:
                k, d = float(stats["Kills"]), float(stats["Deaths"])
                if not k.is_integer() or not d.is_integer() or k < 0 or d < 0:
                    raise ValueError()
            except (KeyError, ValueError, TypeError, OverflowError):
                raise ApiError("Kills/deaths ausentes ou inválidos.") from None
            round_stats = map_data.get("round_stats", {})
            signature = (int(k), int(d), round_stats.get("Map"), round_stats.get("Score"), round_stats.get("Rounds"))
            if map_key in seen:
                if seen[map_key] != signature:
                    raise ApiError("Mapa duplicado com estatísticas conflitantes.")
                continue
            seen[map_key] = signature
            kills += int(k)
            deaths += int(d)
            maps += 1
        if not maps:
            raise ApiError("Partida sem estatísticas de mapas.")
        return kills, deaths


    def player_stats(self, player_id, start_ms, end_ms):
        """Paginação oficial (offset até 200), dividindo janelas saturadas."""
        def window(lo, hi):
            items, seen = [], set()
            for offset in (0, 100, 200):
                payload = self.get(f"/players/{quote(player_id, safe='')}/games/cs2/stats",
                                   {"from": lo, "to": hi, "offset": offset, "limit": 100})
                page = payload.get("items")
                if not isinstance(page, list):
                    raise ApiError("Resposta de estatísticas sem items.")
                keys = [(r.get("stats", {}).get("Match Id"), r.get("stats", {}).get("Match Round")) for r in page]
                if any(not k[0] for k in keys):
                    raise ApiError("Estatística sem identificador da partida.")
                if page and set(keys).issubset(seen):
                    raise ApiError("Paginação de estatísticas repetida.")
                seen.update(keys)
                items.extend(page)
                if len(page) < 100:
                    return items
            if hi - lo <= 86400000:
                raise ApiError("Mais de 300 registros de estatísticas em um dia; usar consulta por partida.")
            middle = (lo + hi) // 2
            return window(lo, middle) + window(middle, hi)
        result = {}
        for item in window(start_ms, end_ms):
            stats = item["stats"]
            # Retém versões divergentes para reconciliação no endpoint da partida.
            # Séries externas ao matchmaking podem repetir número de mapa.
            key = (stats["Match Id"], stats.get("Match Round"), json.dumps(stats, sort_keys=True))
            result[key] = stats
        return list(result.values())
