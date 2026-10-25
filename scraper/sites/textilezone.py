"""textilezone.in — same Astro storefront as vardanethnic.in, plus a reliable per-size stock table."""
import re

from common import clean, in_budget, record
from sites.vardanethnic import _is_readymade, _listing, _product, _stitched

SITE, SITE_NAME = "textilezone", "Textile Zone"
BASE = "https://textilezone.in"
PAKISTANI_CATEGORY = "/wholesale-pakistani-readymade-suits/"
READYMADE_CATEGORY = "/wholesale-readymade-suits/"  # all styles; keep only Pakistani-style items
PAKISTANI = re.compile(r"pakistan|karachi", re.I)


def _stock(page):
    """True/False from the "Available Stock" table, None when the page has no such table."""
    for table in page.find_all("table"):
        head = clean(table.find("thead"))
        if "Available Stock" not in head:
            continue
        cells = [clean(tr.find_all("td")[1]).lower() for tr in table.select("tbody tr")
                 if len(tr.find_all("td")) > 1]
        return any("in stock" in c for c in cells)
    return None


def scrape():
    out, seen = [], set()
    for category in (PAKISTANI_CATEGORY, READYMADE_CATEGORY):
        for url, title, price, pieces in _listing(BASE, category):
            if url in seen or not in_budget(price, pieces) or not _stitched(title, url):
                continue
            seen.add(url)
            p = _product(url)
            p["price"], p["pieces"] = p["price"] or price, p["pieces"] or pieces
            if not in_budget(p["price"], p["pieces"]) or not _is_readymade(p, url):
                continue
            details = " ".join([url, p["title"], p["description"], str(p["ld"].get("category", "")),
                                " ".join(p["alts"])])
            if category == READYMADE_CATEGORY and not PAKISTANI.search(details):
                continue
            in_stock = _stock(p["page"])
            if in_stock is False:
                continue
            out.append(record(
                site=SITE, site_name=SITE_NAME, slug=url.rstrip("/").rsplit("/", 1)[-1],
                title=p["title"], url=url, pieces=p["pieces"], price_per_piece=p["price"],
                set_price=p["set_price"], gst_note=p["gst_note"], brand=p["brand"],
                fabric=p["fabric"], work=p["work"], sizes=p["sizes"],
                description=p["description"], specs=p["rows"], images=p["images"],
                image_alts=p["alts"], in_stock=in_stock,
                stock_reliable=in_stock is not None, category=category,
            ))
    return out
