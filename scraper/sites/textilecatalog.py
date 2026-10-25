"""textilecatalog.in — CakePHP storefront, parsed from HTML."""
import re

import requests

from common import clean, fetch, in_budget, record, soup, to_int

SITE, SITE_NAME = "textilecatalog", "Textile Catalog"
BASE = "https://textilecatalog.in"
# category path -> what every item in it already is (the other trait is checked per item)
CATEGORIES = {"readymade-dresses": "readymade", "wholesale-pakistani-salwar-suits": "pakistani"}
NOT_STITCHED = re.compile(r"dress material|unstitch|semi[- ]?stitch", re.I)
READYMADE = re.compile(r"ready ?made|stitched", re.I)
PAKISTANI = re.compile(r"\bpakis|karachi", re.I)
NOT_SUIT = re.compile(r"jump ?suit|gown|kids|co[- ]?ord|lehenga|saree", re.I)
SKIP_SPECS = {"NAME", "Sku", "WEIGHT"}


def _card_fields(card):
    """Listing card spans look like "MOQ : Minimum 3 Pic" -> {"MOQ": "Minimum 3 Pic"}."""
    fields = {}
    for span in card.select("span.product-new-price-item"):
        text = clean(span)
        if ":" in text:
            key, val = text.split(":", 1)
            fields[key.strip()] = val.strip()
    return fields


def _listing(category):
    for page in range(1, 100):
        try:
            html = fetch(f"{BASE}/{category}?page={page}&limit=100", max_age_hours=24)
        except requests.HTTPError:  # past the last page the site answers 404
            return
        cards = soup(html).select("div.product-item-wrapper")
        if not cards:
            return
        for card in cards:
            link = card.select_one("a[href^='/p/']")
            if not link:
                continue
            f = _card_fields(card)
            pieces, set_price = to_int(f.get("MOQ")), to_int(f.get("Price"))
            # In these paged fragments "Price" is the full catalog price, not per piece.
            price = round(set_price / pieces) if set_price and pieces else None
            yield {"url": BASE + link["href"], "title": clean(card.select_one(".view-abns")),
                   "pieces": pieces, "price": price}


def _specs(page):
    rows = []
    for tr in page.select("table.products_details tr"):
        cells = [clean(c) for c in tr.find_all(["th", "td"])]
        if len(cells) >= 2 and cells[0]:
            rows.append([cells[0].rstrip(": ").strip(), cells[1].rstrip(", ")])
    return rows


def scrape():
    out, seen = [], set()
    for category, kind in CATEGORIES.items():
        for it in _listing(category):
            if (it["url"] in seen or not in_budget(it["price"], it["pieces"])
                    or NOT_STITCHED.search(it["title"]) or NOT_SUIT.search(it["title"])):
                continue
            seen.add(it["url"])
            page = soup(fetch(it["url"]))
            specs = _specs(page)
            spec = dict(specs)
            title = clean(page.select_one("h1")) or spec.get("NAME") or it["title"]
            details = " ".join([title, spec.get("TYPE", ""), spec.get("Fabric", "")])
            if NOT_STITCHED.search(details):
                continue
            if kind == "pakistani" and not ("Size" in spec or READYMADE.search(details)):
                continue
            if kind == "readymade" and not PAKISTANI.search(details):
                continue
            stock = clean(page.select_one("span.stockbuton")).lower()  # "In Stock" / "Out Of Stock"
            if "out" in stock:
                continue
            pieces = to_int(spec.get("MOQ")) or to_int(spec.get("TOTAL DESIGN")) or it["pieces"]
            price = to_int(spec.get("AVG. RATE")) or it["price"]
            if not in_budget(price, pieces):
                continue
            images = [a.get("href") for a in page.select("a.MagicThumb")
                      if (a.get("href") or "").startswith("http")]
            fabric = spec.get("Fabric", "")
            out.append(record(
                site=SITE, site_name=SITE_NAME, slug=it["url"].rsplit("/", 1)[-1],
                title=title, url=it["url"],
                pieces=pieces, price_per_piece=price,
                set_price=to_int(spec.get("FULL CATALOG RATE")),
                gst_note="+5% GST" if "GST" in spec.get("FULL CATALOG RATE", "") else "",
                brand=spec.get("BRAND", ""),
                fabric=fabric.split("|")[0].replace("Top:", "").strip() if "Top:" in fabric else fabric,
                sizes=spec.get("Size", ""), description=fabric,
                specs=[[k.title() if k.isupper() else k, v] for k, v in specs if k not in SKIP_SPECS],
                images=images, in_stock=True if "in stock" in stock else None,
                stock_reliable="in stock" in stock, category=category,
            ))
    return out
