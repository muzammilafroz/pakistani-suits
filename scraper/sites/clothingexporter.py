"""clothingexporter.com — server-rendered catalog pages (60 cards per ?page=N)."""
import re

from common import clean, fetch, in_budget, json_ld, record, soup, to_int

SITE, SITE_NAME = "clothingexporter", "Clothing Exporter"
BASE = "https://clothingexporter.com"
CATEGORIES = ["/collections/pakistani-readymade-suits-wholesale",
              "/collections/pakistani-suits-single-pieces"]
NOT_STITCHED = re.compile(r"un-?stitch|semi-?stitch|dress material", re.I)


def _rows(table):
    return [[clean(c[0]), clean(c[1])] for c in (r.find_all(["td", "th"]) for r in table.select("tr"))
            if len(c) >= 2]


def _listing(category):
    """Yield (title, url, card fields) for in-stock cards that pass the cheap price/pieces check."""
    seen = set()
    for page in range(1, 100):
        cards = soup(fetch(f"{BASE}{category}?page={page}", max_age_hours=24)).select("div.card-product")
        new = [c for c in cards if c.select_one("a.title.link")["href"] not in seen]
        if not new:
            return
        for c in new:
            link = c.select_one("a.title.link")
            seen.add(link["href"])
            fields = dict(_rows(c.select_one("table.product-card-table") or soup("")))
            if clean(c.select_one("div.on-sale-item")).lower() == "stock out":
                continue
            if not in_budget(to_int(c.get("data-price")), to_int(fields.get("MOQ"))):
                continue
            # The single-pieces collection mixes in dress material; stitched items carry a Size row.
            if "single-pieces" in category and "Size" not in fields:
                continue
            yield clean(link), link["href"], fields


def _product(title, url, category):
    page = soup(fetch(url))
    specs = _rows(page.select_one("table.detail-table") or soup(""))
    specs = [[k, re.sub(r"\s*\|\s*", ", ", v) if k == "Size" else v] for k, v in specs]
    spec = dict(specs)
    price, pieces = to_int(spec.get("Per Piece Price")), to_int(spec.get("Total Design"))
    if not in_budget(price, pieces):
        return None
    gst = re.search(r"\+\s*([\d.]+)\s*%\s*GST", spec.get("Per Piece Price", ""), re.I)
    images = []
    for obj in json_ld(page):
        img = obj.get("image") or []
        images += [img] if isinstance(img, str) else img
    images += [i.get("data-src") for i in page.select("img.img-list[data-src]")]
    return record(
        site=SITE, site_name=SITE_NAME, slug=url.rstrip("/").rsplit("/", 1)[-1],
        title=title, url=url, pieces=pieces, price_per_piece=price,
        set_price=to_int(spec.get("Full Catalog Price")),
        gst_note=f"+{gst.group(1)}% GST" if gst else "",
        fabric=re.sub(r"\s*,\s*", ", ", spec.get("Fabric", "")),
        work=spec.get("Work", ""),
        sizes=spec.get("Size", ""),
        description=spec.get("Details", ""),
        specs=[r for r in specs if r[0] not in ("Brand", "Catalog Name")],
        images=[re.sub(r"(?<!:)//+", "/", i.split("?")[0]) for i in images if i],
        in_stock=True, stock_reliable=True, category=category,
    )


def scrape():
    out, seen = [], set()
    for category in CATEGORIES:
        for title, url, _ in _listing(category):
            if url in seen or NOT_STITCHED.search(title):
                continue
            seen.add(url)
            rec = _product(title, url, category)
            if rec:
                out.append(rec)
    return out
