"""Scrape the wholesale sites and build docs/data/suits.json.

    python scraper/build.py scrape [site ...]   # refresh raw per-site output in scraper/data/
    python scraper/build.py build               # filter, dedupe, colour swatches -> docs/data/suits.json
    python scraper/build.py                     # both

The weekly GitHub Actions job runs the last form. scraper/data/ is committed so that a site that
fails or gets blocked keeps its last good results (for up to STALE_DAYS) instead of vanishing.
"""
import importlib
import json
import re
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from itertools import zip_longest

from colors import swatches, text_colours
from common import CACHE, ROOT, image_ok, in_budget

DOCS_DATA = ROOT.parent / "docs" / "data"
SITES = ["textileexport", "clothingexporter", "vardanethnic", "textilecatalog",
         "theethnicworld", "wholesalecatalogz", "textilezone"]
OUT = ROOT / "data"
MIN_SUITS = 100          # refuse to publish a smaller list
SHRINK_LIMIT = 0.5       # a site returning under half its previous count is treated as a bad scrape
STALE_DAYS = 30          # drop a site's fallback records once they are this old
IMAGE_RECHECK_DAYS = 6


def scrape(names):
    OUT.mkdir(parents=True, exist_ok=True)
    for name in names:
        path = OUT / f"{name}.json"
        previous = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
        print(f"[{name}] scraping...", flush=True)
        try:
            records = importlib.import_module(f"sites.{name}").scrape()
        except Exception:
            traceback.print_exc()
            print(f"[{name}] FAILED — keeping the previous {len(previous)} records")
            continue
        if len(previous) >= 10 and len(records) < SHRINK_LIMIT * len(previous):
            print(f"[{name}] only {len(records)} records vs {len(previous)} last time — "
                  f"probably blocked or changed; keeping the previous records")
            continue
        path.write_text(json.dumps(records, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"[{name}] {len(records)} candidate records")


NOT_STITCHED = re.compile(r"un-?stitch|semi[- ]?stitch|dress material", re.I)
EMBROIDERY = re.compile(
    r"embroi|thread|zari|sequin|sequen|mirror|aari|resham|chikan|cut ?work|gota|dori|kasab|"
    r"stone|hand ?work|lace|kantha|schiff?l|applique|patch ?work|khatli|zardo[sz]i|mukaish|diamond",
    re.I)
PRINT_ONLY = re.compile(r"\bprint|\bplain\b|solid colou?r", re.I)
NOT_A_SUIT = re.compile(r"kaftan|co-?ord|gown|jump ?suit|lehenga|saree|\bkids?\b|night ?suit", re.I)
KURTI_STYLE = re.compile(r"kurti|tunic", re.I)
TITLE_STOP = set("""readymade ready made pakistani pakistan karachi suit suits salwar kameez designer
    embroidered embroidery collection catalog catalogue wholesale new latest heavy party wear fancy
    dress dresses set with by the and of a to stitched premium exclusive original d no dno design
    vol volume pcs pc piece pieces single""".split())


def is_embroidered(r):
    """Embroidery mentioned, or at least not described as print-only (most listings omit 'work')."""
    text = " ".join([r["title"], r["work"], r["description"]] + [v for _, v in r["specs"]])
    return bool(EMBROIDERY.search(text)) or not PRINT_ONLY.search(f'{r["title"]} {r["work"]}')


def is_suit(r):
    """Salwar-suit style: no kaftans/gowns/co-ords, and kurti or tunic sets only when they come with a dupatta."""
    if NOT_A_SUIT.search(r["title"]):
        return False
    if KURTI_STYLE.search(r["title"]):
        text = " ".join([r["title"], r["description"]] + [f"{k} {v}" for k, v in r["specs"]])
        return "dupatta" in text.lower() or "duptta" in text.lower()
    return True


def design_key(r):
    """brand + design number + design letters + pieces, e.g. 'hoortex-957ab-2'.

    None when the title has no clear brand and design number (such items are never merged).
    """
    title = r["title"].lower()
    for m in re.finditer(r"\b(\d{2,6})\b", title):
        rest = title[m.end():]
        if re.match(r"\s*(pcs?|pieces?|%)\b", rest):
            continue
        brand = [w for w in re.findall(r"[a-z]+", title[:m.start()]) if w not in TITLE_STOP][:2]
        if not brand:
            return None
        lm = (re.match(r"\s*-?\s*\b([a-z])\s*(?:to|and|&|-)\s*([a-z])\b", rest)
              or re.match(r"\s*-?\s*\b([a-z])\b(?!\s*(?:to|and|&|-)\b)", rest))
        letters = "".join(lm.groups()) if lm else ""
        return f"{''.join(brand)}-{m.group(1)}{letters}-{r['pieces']}"
    return None


def check_images(records):
    """Drop dead image links (results cached for IMAGE_RECHECK_DAYS)."""
    cache_path = CACHE / "imgcheck.json"
    known = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    fresh_since = (date.today() - timedelta(days=IMAGE_RECHECK_DAYS)).isoformat()
    known = {u: v for u, v in known.items() if isinstance(v, list) and v[1] >= fresh_since}
    todo = sorted({u for r in records for u in r["images"] if u not in known})
    print(f"checking {len(todo)} image links...", flush=True)
    with ThreadPoolExecutor(max_workers=8) as pool:
        for url, ok in zip(todo, pool.map(image_ok, todo)):
            known[url] = [ok, date.today().isoformat()]
    CACHE.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(known), encoding="utf-8")
    for r in records:
        keep = [(u, a) for u, a in zip_longest(r["images"], r["imageAlts"][:len(r["images"])])
                if known.get(u, [False])[0]]
        r["images"] = [u for u, _ in keep]
        r["imageAlts"] = [a or "" for _, a in keep] if r["imageAlts"] else []
    return [r for r in records if r["images"]]


def build():
    stats, pool = {}, []
    for name in SITES:
        path = OUT / f"{name}.json"
        if not path.exists():
            print(f"[{name}] no scraped output, skipped")
            continue
        recs = json.loads(path.read_text(encoding="utf-8"))
        s = stats[name] = {"scraped": len(recs)}
        oldest_ok = (date.today() - timedelta(days=STALE_DAYS)).isoformat()
        if recs and max(r["scrapedAt"] for r in recs) < oldest_ok:
            print(f"[{name}] data older than {STALE_DAYS} days — left out")
            recs = []
        recs = list({r["url"]: r for r in recs}.values())
        recs = [r for r in recs if not NOT_STITCHED.search(r["title"] + " " + r["description"])]
        s["stitched"] = len(recs)
        recs = [r for r in recs if in_budget(r["pricePerPiece"], r["pieces"])]
        s["budget+set<=3"] = len(recs)
        recs = [r for r in recs if not (r["stockReliable"] and r["inStock"] is False)]
        s["in stock"] = len(recs)
        recs = [r for r in recs if is_embroidered(r)]
        s["embroidered"] = len(recs)
        recs = [r for r in recs if is_suit(r)]
        s["suit style"] = len(recs)
        pool += recs

    # merge the same catalog listed on several sites; never merge within one site
    groups, merged = {}, []
    for r in pool:
        key = design_key(r)
        if key:
            groups.setdefault(key, []).append(r)
        else:
            merged.append(r)
    for recs in groups.values():
        recs.sort(key=lambda r: (not (r["stockReliable"] and r["inStock"]), r["pricePerPiece"],
                                 -len(r["images"])))
        winner, sites_used = recs[0], {recs[0]["site"]}
        winner["alsoOn"] = []
        for other in recs[1:]:
            if other["site"] in sites_used:
                merged.append(other)
                continue
            sites_used.add(other["site"])
            winner["alsoOn"].append({k: other[k] for k in ("siteName", "url", "pricePerPiece", "gstNote")})
        merged.append(winner)
    print(f"after cross-site merge: {len(pool)} -> {len(merged)}")

    merged = check_images(merged)
    by_site = {}
    for r in merged:
        by_site[r["site"]] = by_site.get(r["site"], 0) + 1
    for name, s in stats.items():
        s["final"] = by_site.get(name, 0)

    suits = []
    for r in sorted(merged, key=lambda r: (r["pricePerPiece"], r["title"])):
        r["colors"] = swatches(text_colours(r["title"], *r["imageAlts"]))
        r["description"] = r["description"][:1500]
        for k in ("category", "brand"):
            r.pop(k, None)
        r.setdefault("alsoOn", [])
        suits.append(r)

    cols = ["scraped", "stitched", "budget+set<=3", "in stock", "embroidered", "suit style", "final"]
    print(f"\n{'site':<18}" + "".join(f"{c:>15}" for c in cols))
    for name, s in stats.items():
        print(f"{name:<18}" + "".join(f"{s.get(c, ''):>15}" for c in cols))
    if len(suits) < MIN_SUITS:
        sys.exit(f"\nERROR: only {len(suits)} suits (minimum {MIN_SUITS}) — suits.json left unchanged")

    DOCS_DATA.mkdir(parents=True, exist_ok=True)
    payload = {"generatedAt": date.today().isoformat(), "count": len(suits), "suits": suits}
    (DOCS_DATA / "suits.json").write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                                          encoding="utf-8")
    print(f"\nTOTAL suits written: {len(suits)} -> {DOCS_DATA / 'suits.json'}")


if __name__ == "__main__":
    args = sys.argv[1:]
    cmd = args[0] if args else "all"
    if cmd in ("scrape", "all"):
        scrape(args[1:] or SITES)
    if cmd in ("build", "all"):
        build()
