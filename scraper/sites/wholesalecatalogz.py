"""wholesalecatalogz.com — OpenCart (Journal3) storefront, parsed from HTML."""
import re

from common import clean, fetch, in_budget, json_ld, record, soup, to_int

SITE, SITE_NAME = "wholesalecatalogz", "Wholesale Catalogz"
BASE = "https://www.wholesalecatalogz.com"
# category path -> whether every item in it is already readymade
CATEGORIES = {"pakistani-ready-made-suits-wholesaler-in-surat": True,
              "single-pakistani-suit": False}
NOT_STITCHED = re.compile(r"dress material|unstitch|semi[- ]?stitch", re.I)
READYMADE = re.compile(r"ready ?made|redaymade|stitched", re.I)
NOT_SUIT = re.compile(r"jump ?suit|gown|kids|co[- ]?ord|lehenga|saree", re.I)
SKIP_SPECS = {"Category Name", "Total Weight"}


def _listing(category):
    page = soup(fetch(f"{BASE}/{category}?limit=300", max_age_hours=24))
    for card in page.select("div.product-layout"):
        link = card.select_one(".name a")
        moq = card.select_one(".moq-lable")
        price = card.select_one(".price-new") or card.select_one(".price-normal")
        if not (link and moq and price):
            continue
        yield {"url": link["href"].split("?")[0], "title": clean(link),
               "pieces": to_int(moq.get_text().split(":")[-1]), "price": to_int(price.get_text())}


def _specs(page):
    rows = []
    for tr in page.select("table.attribute tr"):
        cells = [clean(c) for c in tr.find_all(["th", "td"])]
        if len(cells) >= 2 and cells[0]:
            rows.append([cells[0].rstrip(":").strip(), cells[1]])
    return rows


def scrape():
    out, seen = [], set()
    for category, all_readymade in CATEGORIES.items():
        for it in _listing(category):
            if (it["url"] in seen or not in_budget(it["price"], it["pieces"])
                    or NOT_STITCHED.search(it["title"]) or NOT_SUIT.search(it["title"])):
                continue
            seen.add(it["url"])
            page = soup(fetch(it["url"]))
            specs = _specs(page)
            spec = dict(specs)
            kind = spec.get("Type", "")
            if NOT_STITCHED.search(kind):
                continue
            if not all_readymade and not ("Size" in spec or READYMADE.search(it["title"] + " " + kind)):
                continue
            if "out of stock" in spec.get("Availability", "").lower():
                continue
            pieces = to_int(spec.get("MOQ")) or it["pieces"]
            price = to_int(spec.get("Per Piece Rate")) or it["price"]
            if not in_budget(price, pieces):
                continue
            images = [a.get("href") for a in page.select('a[data-fancybox="gallery"]')]
            if not images:
                images = [ld.get("image") for ld in json_ld(page) if isinstance(ld.get("image"), str)]
            h1 = page.select_one("h1")
            description = " ".join(x for x in [spec.get("Note", ""), spec.get("Fabrics", "")] if x)
            out.append(record(
                site=SITE, site_name=SITE_NAME, slug=it["url"].rsplit("/", 1)[-1],
                title=clean(h1) or it["title"], url=it["url"],
                pieces=pieces, price_per_piece=price, set_price=to_int(spec.get("Catalog Price")),
                brand=spec.get("Brand", ""), fabric=spec.get("Fabric", ""), work=spec.get("Work", ""),
                sizes=spec.get("Size", ""), description=description,
                specs=[[k, v] for k, v in specs if k not in SKIP_SPECS],
                images=images, in_stock=True, stock_reliable=True, category=category,
            ))
    return out
