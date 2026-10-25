"""theethnicworld.com — server-rendered catalog pages (60 cards per ?page=N, 404 past the end)."""
import re

import requests

from common import clean, fetch, in_budget, record, soup, to_int

SITE, SITE_NAME = "theethnicworld", "The Ethnic World"
BASE = "https://theethnicworld.com"
CATEGORIES = ["/wholesale-readymade-suits", "/readymade-salwar-suits"]
NOT_STITCHED = re.compile(r"un-?stitch|semi-?stitch|dress material", re.I)
PAKISTANI = re.compile(r"pakistan|karachi", re.I)


def _listing(category):
    """Yield (title, url) for cards that pass the cheap price/pieces check."""
    seen = set()
    for page in range(1, 100):
        try:
            cards = soup(fetch(f"{BASE}{category}?page={page}", max_age_hours=24)).select("div.card-product")
        except requests.HTTPError:
            return  # the site answers 404 past the last page
        new = [c for c in cards if c.select_one("a.title.link")["href"] not in seen]
        if not new:
            return
        for c in new:
            link = c.select_one("a.title.link")
            seen.add(link["href"])
            vals = [clean(d) for d in c.select("div.catalog-list > div")]
            price = to_int(vals[0]) if vals else None
            pieces = next((to_int(v) for v in vals if v.lower().startswith("pcs")), None)
            if in_budget(price, pieces):
                yield clean(link), BASE + link["href"]


def _product(title, url, category):
    page = soup(fetch(url))
    specs = [[clean(r.select_one("th.tf-attr-label")), clean(r.select_one("td.tf-attr-value"))]
             for r in page.select("tr") if r.select_one("th.tf-attr-label")]
    spec = dict(specs)
    details = " ".join(clean(e) for e in page.select("div.fbric"))
    details = re.sub(r"^Fabric\s*-\s*", "", details)
    if not PAKISTANI.search(f"{url} {title} {details}"):
        return None
    price, pieces = to_int(spec.get("Per Piece Price")), to_int(spec.get("Total Design"))
    if not in_budget(price, pieces):
        return None
    gst = re.search(r"\+\s*([\d.]+)\s*%\s*GST", spec.get("Per Piece Price", ""), re.I)
    picker = page.select_one(".tf-product-info-variant-picker .variant-picker-item")
    sizes = ", ".join(s.upper() for s in clean(picker).split()) if picker else ""
    if sizes:
        specs.append(["Size", sizes])
    specs += [[part.split(":", 1)[0], part.split(":", 1)[1]]
              for part in details.split("|") if ":" in part]
    return record(
        site=SITE, site_name=SITE_NAME, slug=url.rstrip("/").rsplit("/", 1)[-1],
        title=title, url=url, pieces=pieces, price_per_piece=price,
        set_price=to_int(spec.get("Catalog Price")),
        gst_note=f"+{gst.group(1)}% GST" if gst else "",
        brand="" if spec.get("Brand") == "Wholesale Market Surat" else spec.get("Brand", ""),
        fabric=spec.get("Fabric", ""), sizes=sizes,
        description=details,
        specs=[r for r in specs if r[0] not in ("Catalog No", "Brand")],
        images=[i.get("data-zoom") or i.get("src") for i in page.select("img.tf-image-zoom")],
        in_stock=None, stock_reliable=False, category=category,
    )


def scrape():
    out, seen = [], set()
    for category in CATEGORIES:
        for title, url in _listing(category):
            if url in seen or NOT_STITCHED.search(title):
                continue
            seen.add(url)
            rec = _product(title, url, category)
            if rec:
                out.append(rec)
    return out
