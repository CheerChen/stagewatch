"""Source configurations and parsers.

Each parser function takes a source dict and returns a list of
{id, title, url, published_at} items. Parsers handle their own HTTP.
"""
import hashlib
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from fetch import fetch_json, fetch_text


def _hash_id(*parts: str) -> str:
    return hashlib.md5("|".join(parts).encode("utf-8")).hexdigest()[:12]


# --- JVCMusic / FlyingDog ---

def parse_jvc(src: dict) -> list[dict]:
    if src["kind"] == "artist":
        url = f"https://www.jvcmusic.co.jp/-/Information/{src['id']}.json"
        rows_key = "news"
    elif src["kind"] == "series":
        url = f"https://www.jvcmusic.co.jp/{src['label']}/-/News2/{src['id']}.json?page=1"
        rows_key = "articles"
    else:
        raise ValueError(f"Unknown jvc kind: {src['kind']!r}")

    raw = fetch_json(url)
    rows = (raw.get("contents") or {}).get(rows_key) or []
    items = []
    for row in rows:
        u = (row.get("url") or "").strip()
        t = (row.get("title") or "").strip()
        if not u or not t:
            continue
        items.append({
            "id": u,
            "title": t,
            "url": u,
            "published_at": (row.get("open_dt") or "").strip(),
        })
    return items


# --- RYTHEM (Wix one-page site) ---

_RYTHEM_SKIP_TITLES = {"INFORMATION", "More"}
_HEADING_RE = re.compile(r"^h[1-6]$")


def parse_rythem(src: dict) -> list[dict]:
    """Each news is a section.Oqnisf with a comp-XXXXX class as stable id."""
    html = fetch_text(src["url"])
    soup = BeautifulSoup(html, "html.parser")

    items = []
    for sec in soup.select("section.Oqnisf"):
        classes = sec.get("class") or []
        comp_id = next((c for c in classes if c.startswith("comp-")), None)
        if not comp_id:
            continue

        title = None
        for rt in sec.select(".wixui-rich-text"):
            h = rt.find(_HEADING_RE)
            if h:
                title = h.get_text(" ", strip=True)
                break
        if not title:
            rt = sec.select_one(".wixui-rich-text")
            if rt:
                title = rt.get_text(" ", strip=True)

        if not title or title in _RYTHEM_SKIP_TITLES:
            continue

        # Truncate overly long fallback titles (when only body exists)
        if len(title) > 120:
            title = title[:117] + "..."

        items.append({
            "id": f"rythem:{comp_id}",
            "title": title,
            "url": src["url"],
            "published_at": "",
        })
    return items


# --- 牧野由依 (single-page, no per-item permalink) ---

def parse_yuiyui(src: dict) -> list[dict]:
    html = fetch_text(src["url"])
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for sec in soup.select("section.entry_area"):
        title_el = sec.select_one(".entry_title")
        if not title_el:
            continue
        title = title_el.get_text(" ", strip=True)
        if not title:
            continue
        date_el = sec.select_one(".entry_date")
        date = date_el.get_text(" ", strip=True) if date_el else ""
        items.append({
            "id": f"yuiyui:{_hash_id(date, title)}",
            "title": title,
            "url": src["url"],
            "published_at": date,
        })
    return items


# --- Perfume (per-news permalink via detail.php?id=N) ---

def parse_perfume(src: dict) -> list[dict]:
    html = fetch_text(src["url"])
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for it in soup.select("div.c-news__item"):
        a = it.find("a", href=True)
        if not a:
            continue
        url = urljoin(src["url"], a["href"])
        name_el = it.select_one(".c-news__name")
        title = name_el.get_text(" ", strip=True) if name_el else ""
        if not title:
            continue
        date_el = it.select_one(".c-news__date")
        date = date_el.get_text(" ", strip=True) if date_el else ""
        items.append({
            "id": url,
            "title": title,
            "url": url,
            "published_at": date,
        })
    return items


# --- 水樹奈々 (JSON list, single-page UI; no per-news permalink) ---

def parse_mizuki(src: dict) -> list[dict]:
    raw = fetch_json(src["api_url"])
    items = []
    for row in raw.get("articles") or []:
        aid = row.get("id")
        title = (row.get("title") or "").strip()
        if aid is None or not title:
            continue
        items.append({
            "id": f"mizuki:{aid}",
            "title": title,
            "url": src["url"],
            "published_at": (row.get("date") or "").strip(),
        })
    return items


# --- KOTOKO (NBCUniversal table-based news list, with permalink) ---

def parse_kotoko(src: dict) -> list[dict]:
    html = fetch_text(src["url"])
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for row in soup.select("tr"):
        title_a = row.select_one("td.read .title a[href]")
        if not title_a:
            continue
        url = urljoin(src["url"], title_a["href"])
        title = title_a.get_text(" ", strip=True)
        if not title:
            continue
        date_el = row.select_one("td.day")
        date = date_el.get_text(" ", strip=True) if date_el else ""
        items.append({
            "id": url,
            "title": title,
            "url": url,
            "published_at": date,
        })
    return items


# --- Generic WordPress (post-NNN containers + entry-title links) ---

def parse_wordpress(src: dict) -> list[dict]:
    html = fetch_text(src["url"])
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for post in soup.find_all(id=lambda x: x and x.startswith("post-")):
        title_a = post.select_one(".entry-title a, h1 a, h2 a, h3 a")
        if not title_a or not title_a.get("href"):
            continue
        url = urljoin(src["url"], title_a["href"])
        title = title_a.get_text(" ", strip=True)
        if not title:
            continue
        items.append({
            "id": url,
            "title": title,
            "url": url,
            "published_at": "",
        })
    return items


# --- TWICE Japan (newsList ul + per-news detail URL) ---

def parse_twice(src: dict) -> list[dict]:
    html = fetch_text(src["url"])
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for li in soup.select("ul.newsList > li"):
        a = li.find("a", href=True)
        if not a:
            continue
        url = urljoin(src["url"], a["href"])
        tit_el = a.select_one(".tit")
        title = " ".join(tit_el.get_text(" ", strip=True).split()) if tit_el else ""
        if not title:
            continue
        items.append({
            "id": url,
            "title": title,
            "url": url,
            "published_at": "",
        })
    return items


# --- Registry ---

PARSERS = {
    "jvc": parse_jvc,
    "rythem": parse_rythem,
    "yuiyui": parse_yuiyui,
    "perfume": parse_perfume,
    "mizuki": parse_mizuki,
    "kotoko": parse_kotoko,
    "twice": parse_twice,
    "wordpress": parse_wordpress,
}


SOURCES = [
    {"name": "坂本真綾", "parser": "jvc", "kind": "artist", "id": "A008957"},
    {"name": "YENA", "parser": "jvc", "kind": "artist", "id": "A029411"},
    {"name": "マクロスF", "parser": "jvc", "kind": "series", "id": "Z0221", "label": "flyingdog"},
    {"name": "RYTHEM", "parser": "rythem", "url": "https://www.rythem.jp/info"},
    {"name": "牧野由依", "parser": "yuiyui", "url": "https://www.yuiyuimakino.com/news/index.php"},
    {"name": "Perfume Live", "parser": "perfume", "url": "https://www.perfume-web.jp/news/live.php"},
    {
        "name": "水樹奈々",
        "parser": "mizuki",
        "url": "https://www.mizukinana.jp/news/",
        "api_url": "https://www.mizukinana.jp/news/100.json",
    },
    {"name": "KOTOKO", "parser": "kotoko", "url": "https://nbcuni-music.com/kotoko/news/list00010000.html"},
    {"name": "TWICE Live", "parser": "twice", "url": "https://www.twicejapan.com/schedule/list/4"},
    {
        "name": "AQUAPLUS Event (WHITE ALBUM)",
        "parser": "wordpress",
        "url": "https://blog.aquaplus.jp/category/info/event",
        "title_includes": "WHITE ALBUM",
    },
]
