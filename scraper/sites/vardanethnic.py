"""vardanethnic.in — Astro storefront: HTML listing cards, product spec table + JSON-LD.

textilezone.in runs the same template, so the listing/product helpers here are shared with it.
"""
import html
import re
from urllib.parse import urljoin

from common import clean, fetch, in_budget, json_ld, record, soup, to_int

SITE, SITE_NAME = "vardanethnic", "Vardan Ethnic"
BASE = "https://vardanethnic.in"
CATEGORY = "/wholesale-readymade-pakistani-suits/"

NOT_STITCHED = re.compile(r"un-?stit?ch|semi[- ]?stit?ch|dress[- ]material|fabric[- ]catalog"
                          r"|top[- ]bottom[- ](dupatta[- ])?fabric", re.I)
SIZED = re.compile(r"\b(XS|S|M|L|XL|XXL|XXXL|[2-6]XL|\d{2})\b", re.I)
READYMADE = re.compile(r"ready[- ]?made|\bstitched", re.I)


def _page(url, **kw):
    """Fetch + parse. These sites send no charset, so undo a latin-1 mis-decode of UTF-8 if present."""
    text = fetch(url, **kw)
    try:
        text = text.encode("latin-1").decode("utf-8")
    except UnicodeError:
        pass
    return soup(text)


def _listing(base, category):
    """Yield (url, title, price_per_piece, pieces) for every card on every page of a category."""
    first = _page(base + category, max_age_hours=24)
    pages = [int(n) for n in re.findall(rf"{re.escape(category)}page/(\d+)/", str(first))]
    seen = set()
    for n in range(1, max(pages or [1]) + 1):
        page = first if n == 1 else _page(f"{base}{category}page/{n}/", max_age_hours=24)
        for price in page.select("span[data-price-inr]"):
            card = price.find_parent("div", class_="group")
            link = card.find("a", href=True) if card else None
            if not link:
                continue
            url = urljoin(base, link["href"])
            if url in seen:
                continue
            seen.add(url)
            moq = next((s.find_next_sibling("span") for s in card.find_all("span")
                        if clean(s) == "MOQ:"), None)
            title = clean(card.find("p")) or link.get("aria-label", "")
            yield url, title, to_int(price["data-price-inr"]), to_int(clean(moq))


def _spec_rows(page):
    """[label, value] rows from the spec table (vardan) or the "Label: value" list (textilezone)."""
    rows = []
    for th in page.select("th[scope=row]"):
        td = th.find_next_sibling("td")
        if td:
            for junk in td.find_all(["span", "script", "button"]):
                junk.decompose()
            value = re.sub(r"\s*\b(Size\s+)?Chart\b.*$", "", clean(td))
            rows.append([clean(th), value])
    if not rows:
        for li in page.select("li"):
            label = li.find("strong")
            if label and clean(label).endswith(":"):
                rows.append([clean(label).rstrip(":"), clean(li)[len(clean(label)):].strip()])
    return [[k, v] for k, v in rows if k and v and k.lower() != "product name"]


def _row(rows, *labels):
    for label in labels:
        for k, v in rows:
            if k.lower() == label.lower():
                return v
    return ""


def _image_key(url):
    """Same photo is sometimes listed as .webp and .jpeg; compare without the extension."""
    return re.sub(r"(\.(webp|jpe?g|png))+$", "", url.lower())


def _product(url):
    """Parse a product page into the fields shared by both sites."""
    page = _page(url)
    ld = (json_ld(page) or [{}])[0]
    rows = _spec_rows(page)
    h1 = page.find("h1")

    # Map each full-size photo to its alt text (alts sit on the "-thumb" variants too).
    alts = {}
    for img in page.find_all("img", src=True):
        full = re.sub(r"-thumb(\.\w+)$", r"\1", img["src"])
        if img.get("alt") and full not in alts:
            alts[full] = clean(img["alt"])
    images, keys = [], set()
    ld_images = ld.get("image") or []
    for u in [ld_images] if isinstance(ld_images, str) else ld_images:
        if _image_key(u) not in keys:
            keys.add(_image_key(u))
            images.append(u)

    offer = ld.get("offers") or {}
    price_txt = _row(rows, "Price Per Pc", "Per Pc Price", "Price Per Piece", "Per Piece Price")
    price = to_int(price_txt) or to_int((offer.get("priceSpecification") or {}).get("price"))
    pieces = (to_int(_row(rows, "No of Pcs", "No. of Pcs", "Total Designs", "Total Design"))
              or to_int((offer.get("eligibleQuantity") or {}).get("value")))
    gst = re.search(r"(\d+)\s*%\s*GST", price_txt)
    desc = page.select_one("div.wp-content")
    brand = _row(rows, "Brand") or (ld.get("brand") or {}).get("name", "")
    return {
        "page": page, "rows": rows, "ld": ld,
        "title": html.unescape(clean(h1) or ld.get("name", "")),
        "images": images, "alts": [alts.get(u, "") for u in images],
        "price": price, "pieces": pieces,
        "set_price": to_int(_row(rows, "Catalog Price", "Full Catalog Price")),
        "gst_note": f"+{gst.group(1)}% GST" if gst else "+5% GST",
        "brand": brand,
        "fabric": _row(rows, "Top", "Top Fabric", "Fabric"),
        "work": _row(rows, "Work"),
        "sizes": _row(rows, "Size", "Sizes"),
        "description": clean(desc),
    }


def _stitched(*texts):
    return not any(NOT_STITCHED.search(t or "") for t in texts)


def _is_readymade(p, url):
    """Stitched suits carry garment sizes (XL, 42…) or say "readymade"; dress material does neither."""
    if not _stitched(p["title"], p["fabric"], p["sizes"]):
        return False
    return bool(SIZED.search(p["sizes"]) or READYMADE.search(p["title"] + " " + url))


def scrape():
    out = []
    for url, title, price, pieces in _listing(BASE, CATEGORY):
        if not in_budget(price, pieces) or not _stitched(title, url):
            continue
        p = _product(url)
        p["price"], p["pieces"] = p["price"] or price, p["pieces"] or pieces
        # "No of Pcs" is sometimes wrong; a set-only catalog whose price is exactly N × per-piece has N pieces.
        implied = p["set_price"] / p["price"] if p["set_price"] and p["price"] else 0
        if "set to set" in _row(p["rows"], "Availability").lower() and abs(implied - round(implied)) < 0.05:
            p["pieces"] = max(p["pieces"] or 0, round(implied))
        if not in_budget(p["price"], p["pieces"]) or not _is_readymade(p, url):
            continue
        out.append(record(
            site=SITE, site_name=SITE_NAME, slug=url.rstrip("/").rsplit("/", 1)[-1],
            title=p["title"], url=url, pieces=p["pieces"], price_per_piece=p["price"],
            set_price=p["set_price"], gst_note=p["gst_note"], brand=p["brand"],
            fabric=p["fabric"], work=p["work"], sizes=p["sizes"],
            description=p["description"], specs=p["rows"], images=p["images"],
            in_stock=None, stock_reliable=False, category=CATEGORY,
        ))
    return out
