"""Shared helpers for the site scrapers: polite cached HTTP, parsing utilities, record shape."""
import hashlib
import json
import pathlib
import re
import time
from datetime import date
from urllib.parse import quote, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

ROOT = pathlib.Path(__file__).resolve().parent
CACHE = ROOT / ".cache"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")
DELAY = 1.0  # seconds between requests to the same host

PRICE_MIN, PRICE_MAX, MAX_PIECES = 1000, 2000, 3

_session = requests.Session()
_session.headers.update({"User-Agent": UA, "Accept-Language": "en-IN,en;q=0.9"})
_last_hit = {}


def _throttle(host):
    wait = DELAY - (time.monotonic() - _last_hit.get(host, 0))
    if wait > 0:
        time.sleep(wait)
    _last_hit[host] = time.monotonic()


def fetch(url, *, method="GET", json_body=None, headers=None, max_age_hours=20):
    """Return the response text, served from the on-disk cache when available."""
    host = urlsplit(url).netloc
    key = hashlib.sha1(f"{method} {url} {json.dumps(json_body, sort_keys=True)}".encode()).hexdigest()
    path = CACHE / "http" / host / key
    if path.exists():
        age_h = (time.time() - path.stat().st_mtime) / 3600
        if max_age_hours is None or age_h < max_age_hours:
            return path.read_text(encoding="utf-8")
    last_err = None
    for attempt in range(3):
        _throttle(host)
        try:
            r = _session.request(method, url, json=json_body, headers=headers, timeout=45)
            r.raise_for_status()
            if "charset" not in r.headers.get("content-type", "").lower():
                r.encoding = "utf-8"  # requests would otherwise assume ISO-8859-1 for text/html
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(r.text, encoding="utf-8")
            return r.text
        except requests.RequestException as e:
            last_err = e
            time.sleep(2 * (attempt + 1))
    raise last_err


def fetch_json(url, **kw):
    return json.loads(fetch(url, **kw))


def image_ok(url):
    """True when the image URL answers with an image (HEAD, falling back to a streamed GET)."""
    for method in ("HEAD", "GET"):
        try:
            r = _session.request(method, url, timeout=30, stream=True, allow_redirects=True)
            r.close()
        except requests.RequestException:
            continue
        if r.status_code == 200 and r.headers.get("content-type", "").startswith("image"):
            return True
        if r.status_code in (404, 410):
            return False
    return False


def soup(html):
    return BeautifulSoup(html, "html.parser")


def clean(s):
    """Collapse whitespace; accepts a string or a bs4 element."""
    if s is None:
        return ""
    if hasattr(s, "get_text"):
        s = s.get_text(" ")
    return re.sub(r"\s+", " ", str(s)).strip()


def to_int(s):
    """First number in the string ("INR 1,399.00" -> 1399), or None."""
    m = re.search(r"\d[\d,]*(?:\.\d+)?", str(s or ""))
    return round(float(m.group().replace(",", ""))) if m else None


def json_ld(page, kind="Product"):
    """All JSON-LD objects of the given @type on a parsed page."""
    found = []
    for tag in page.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or tag.get_text() or "")
        except ValueError:
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            obj = stack.pop()
            if isinstance(obj, list):
                stack.extend(obj)
            elif isinstance(obj, dict):
                if "@graph" in obj:
                    stack.extend(obj["@graph"])
                t = obj.get("@type")
                if t == kind or (isinstance(t, list) and kind in t):
                    found.append(obj)
    return found


def safe_url(url):
    """Percent-encode spaces and other unsafe characters in a URL path."""
    if not url:
        return url
    parts = urlsplit(url.strip())
    return urlunsplit(parts._replace(path=quote(parts.path, safe="/%:@!$&'()*+,;=-._~")))


def dedupe(seq):
    seen, out = set(), []
    for x in seq:
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out


def in_budget(price, pieces):
    return (price is not None and PRICE_MIN <= price <= PRICE_MAX
            and pieces is not None and 1 <= pieces <= MAX_PIECES)


def record(*, site, site_name, slug, title, url, pieces, price_per_piece, images,
           set_price=None, gst_note="", brand="", fabric="", work="", sizes="",
           description="", specs=None, image_alts=None, in_stock=None,
           stock_reliable=False, category=""):
    """Normalised suit record shared by every site module."""
    return {
        "id": f"{site}:{slug}",
        "site": site,
        "siteName": site_name,
        "title": clean(title),
        "url": url,
        "brand": clean(brand),
        "pieces": pieces,
        "pricePerPiece": price_per_piece,
        "setPrice": set_price or (price_per_piece * pieces if price_per_piece and pieces else None),
        "gstNote": gst_note,
        "fabric": clean(fabric),
        "work": clean(work),
        "sizes": clean(sizes),
        "description": clean(description),
        "specs": [[clean(k), clean(v)] for k, v in (specs or []) if clean(k) and clean(v)],
        "images": dedupe(safe_url(u) for u in images),
        "imageAlts": image_alts or [],
        "inStock": in_stock,
        "stockReliable": stock_reliable,
        "category": category,
        "scrapedAt": date.today().isoformat(),
    }
