"""HTTP fetch + state.json persistence."""
import json
from pathlib import Path

import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
}

STATE_FILE = Path(__file__).parent / "state.json"


def fetch_json(url: str, timeout: int = 30) -> dict:
    r = requests.get(url, headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    return r.json()


def fetch_text(url: str, timeout: int = 30) -> str:
    r = requests.get(url, headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    # When server omits charset, requests falls back to ISO-8859-1 which
    # garbles UTF-8/Shift-JIS pages. Use chardet's sniff in that case.
    ct = r.headers.get("content-type", "").lower()
    if r.encoding == "ISO-8859-1" and "charset" not in ct:
        r.encoding = r.apparent_encoding
    return r.text


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
