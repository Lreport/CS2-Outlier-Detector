"""Verifica a conexao com a Data API; nao coleta a base da Season 8."""

import json
import os
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
URL = "https://open.faceit.com/data/v4/rankings/games/cs2/regions/EU?limit=1"


def load_api_key():
    """Prioriza a variavel de ambiente; aceita atribuicao simples no .env."""
    key = os.environ.get("FACEIT_API_KEY", "").strip()
    if key:
        return key
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8-sig").splitlines():
            name, separator, value = line.strip().partition("=")
            if separator and name.strip() == "FACEIT_API_KEY":
                value = value.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
                    value = value[1:-1]
                return value.strip()
    return ""


def main():
    try:
        key = load_api_key()
    except (OSError, UnicodeError):
        print("Nao foi possivel ler o .env. Salve o arquivo como UTF-8.")
        return 1
    if not key:
        print("Preencha FACEIT_API_KEY no arquivo .env da raiz do projeto.")
        return 1
    try:
        request = Request(URL, headers={"Authorization": f"Bearer {key}", "Accept": "application/json"})
        with urlopen(request, timeout=30) as response:
            data = json.load(response)
    except HTTPError as error:
        messages = {
            401: "Chave recusada. Confira a chave server side salva no .env.",
            403: "Acesso negado. Confira as permissoes da chave no portal FACEIT.",
            429: "Limite de consultas atingido. Tente novamente mais tarde.",
        }
        message = messages.get(error.code, "A consulta falhou. Tente novamente mais tarde.")
        print(f"HTTP {error.code}: {message}")
        return 1
    except (URLError, TimeoutError, OSError):
        print("Falha de conexao com a FACEIT. Confira a rede e tente novamente.")
        return 1
    except (ValueError, UnicodeError):
        print("Resposta ou configuracao invalida. Confira a chave e tente novamente.")
        return 1
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        print("A API respondeu, mas o formato do ranking foi inesperado.")
        return 1
    print("Conexao com a FACEIT confirmada.")
    print(f"Registros recebidos na consulta de teste: {len(data['items'])}.")
    print("Este teste consulta o ranking ATUAL de CS2 EU.")
    print("Falta verificar o ranking final da Season 8 e o FACEIT Rating por partida.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

