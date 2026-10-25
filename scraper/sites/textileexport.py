"""textileexport.in — JSON API behind the Next.js storefront."""
from common import clean, fetch_json, in_budget, record, to_int, soup

SITE, SITE_NAME = "textileexport", "Textile Export"
API = "https://backend.textileexport.in/Api/V1"
HEADERS = {"Origin": "https://www.textileexport.in", "Content-Type": "application/json"}
CATEGORY = "pakistani-ready-made-suits-wholesale"


def _listing():
    items, offset = [], 0
    while True:
        body = {"slug": CATEGORY, "limit": 500, "offset": offset, "currency": "IN"}
        data = fetch_json(f"{API}/product_list", method="POST", json_body=body,
                          headers=HEADERS, max_age_hours=24)
        batch = data.get("product") or []
        items += batch
        offset += len(batch)
        if not batch or offset >= int(data.get("count") or 0):
            return items


def scrape():
    out = []
    for it in _listing():
        pieces, price = to_int(it.get("pmoq")), to_int(it.get("pprice"))
        if not in_budget(price, pieces) or str(it.get("isstock")) != "1":
            continue
        p = fetch_json(f"{API}/detail?slug={it['slug']}", headers=HEADERS)["product"]
        attrs = {a["pattr_name"]: a["value"] for a in p.get("pattr") or []}
        desc_html = clean(soup(p.get("pdesc") or "").get_text(" "))
        description = " ".join(x for x in [clean(p.get("pshortdesc")), desc_html] if x)
        specs = [["Pieces in set", f"{pieces}"],
                 ["Per piece price", f"₹{price} + {p.get('ptax_val') or 5}% GST"],
                 ["Full set price", f"₹{to_int(p.get('pcprice'))}"]]
        specs += [[k, v] for k, v in attrs.items()]
        out.append(record(
            site=SITE, site_name=SITE_NAME, slug=it["slug"],
            title=p.get("ptitle") or it.get("ptitle"),
            url=f"https://www.textileexport.in/{it['slug']}",
            pieces=pieces, price_per_piece=price, set_price=to_int(p.get("pcprice")),
            gst_note=f"+{p.get('ptax_val') or 5}% GST",
            fabric=attrs.get("Fabric") or it.get("fabric_text", ""),
            work=attrs.get("Work", ""), sizes=attrs.get("Size") or p.get("size_text", ""),
            description=description, specs=specs,
            images=[p.get("thumbnail")] + list(p.get("pgalary") or []),
            in_stock=True, stock_reliable=True, category=CATEGORY,
        ))
    return out
