"""Telegram bot notification."""
import os

import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
API = f"https://api.telegram.org/bot{TOKEN}/sendMessage"


def notify(source: str, title: str, url: str) -> bool:
    text = f"【{source}】{title}\n{url}"
    try:
        r = requests.post(
            API,
            data={"chat_id": CHAT_ID, "text": text, "disable_web_page_preview": "true"},
            timeout=15,
        )
    except requests.RequestException as e:
        print(f"  ⚠ telegram request failed: {e}")
        return False
    if not r.ok:
        print(f"  ⚠ telegram {r.status_code}: {r.text[:200]}")
        return False
    return True
