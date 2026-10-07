"""Felles oppsett: konfigurasjon, stier, HTTP og små hjelpere."""
import hashlib
import json
import os
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SITE = ROOT / "site"

CONFIG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
YEAR = int(CONFIG["year"])
SOURCE_URL = CONFIG["source_url"]

CACHE = Path(os.path.expanduser(CONFIG.get("cache_dir", "~/.statsbudsjett-cache"))) / str(YEAR)
PDF_DIR = CACHE / "pdf"
PAGES_DIR = CACHE / "pages"
HTML_DIR = CACHE / "html"
DIST = CACHE / "dist"
for d in (PDF_DIR, PAGES_DIR, HTML_DIR, DATA):
    d.mkdir(parents=True, exist_ok=True)

HEADERS = {"User-Agent": "Mozilla/5.0 (statsbudsjett-sok; uoffisiell sokeside; kontakt via github.com/sondreolsen)"}
_session = requests.Session()
_session.headers.update(HEADERS)

HOST = "www.regjeringen.no"


def get(url, binary=False, retries=3):
    for i in range(retries):
        try:
            r = _session.get(url, timeout=60)
            r.raise_for_status()
            time.sleep(0.25)
            return r
        except requests.RequestException:
            if i == retries - 1:
                raise
            time.sleep(2 * (i + 1))


def soup(url):
    r = get(url)
    return BeautifulSoup(r.content, "html.parser"), r.url


def normalize(url, base=None):
    """Absolutt URL uten fragment, og med gjentatte /idNNN/-segmenter fjernet
    (regjeringen.no har lenker som .../id3124140/id3124140/)."""
    u = urljoin(base, url) if base else url
    p = urlsplit(u)
    path = re.sub(r"(/id\d+)(?:\1)+/?", r"\1/", p.path)
    return urlunsplit((p.scheme, p.netloc, path, p.query if not p.query.startswith("mce") else "", ""))


def links(s, base, scope=None):
    """[(tekst, url)] i <main>, uten duplikater, bare regjeringen.no."""
    main = s.find("main") or s
    out, seen = [], set()
    for a in main.find_all("a", href=True):
        href = a["href"].split("#")[0]
        if not href or href.startswith(("mailto:", "tel:", "javascript:")):
            continue
        u = normalize(href, base)
        if urlsplit(u).netloc != HOST or u in seen:
            continue
        seen.add(u)
        out.append((" ".join(a.get_text(" ").split()), u))
    return out


def meta(s, name):
    m = s.find("meta", attrs={"name": name}) or s.find("meta", attrs={"property": name})
    return (m.get("content") or "").strip() if m else ""


def url_key(url):
    return hashlib.sha1(url.encode()).hexdigest()[:12]


def write_json(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path, default=None):
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")
