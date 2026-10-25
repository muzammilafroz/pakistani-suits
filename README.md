# Suit Picker

A phone-friendly gallery of Pakistani-style embroidered **readymade (stitched)** suits sold by Indian
wholesale catalog websites that ship all over India — only listings where the set is **3 pieces or
fewer** and the price is **₹1000–2000 per piece**.

**Live site:** https://muzammilafroz.github.io/pakistani-suits/

Each suit shows all its photos, pieces in the set, per-piece and full-set price, the seller's
details, and a button to the original product page. Hearts (♥) save favourites on the phone, and
"Send" shares a suit on WhatsApp.

Photos are loaded directly from the sellers' websites and belong to them. Prices and stock are a
snapshot — always confirm on the seller's page.

## Sources

| Site | Category |
|---|---|
| textileexport.in | Pakistani ready-made suits (JSON API) |
| clothingexporter.com | Pakistani readymade suits + single pieces |
| vardanethnic.in | Wholesale readymade Pakistani suits |
| textilecatalog.in | Readymade dresses / Pakistani suits |
| theethnicworld.com | Readymade suits (Pakistani-style only) |
| wholesalecatalogz.com | Pakistani ready-made suits + singles |
| textilezone.in | Pakistani readymade suits |

## Refreshing the data

**Automatic:** the [Weekly suit refresh](.github/workflows/refresh.yml) workflow runs every Monday
at 07:00 IST. It re-scrapes all sites, rebuilds `docs/data/suits.json`, commits it and republishes
the site. To refresh right away: Actions → Weekly suit refresh → Run workflow.

Safety checks so a bad run never empties the page:
- if a site errors, or returns under half as many suits as last time, its previous results in
  `scraper/data/` are kept (and dropped once they are 30 days old);
- if fewer than 100 suits remain, the run fails and the live page stays as it was.

**By hand:**

```
python -m venv .venv
.venv\Scripts\python -m pip install -r scraper\requirements.txt
.venv\Scripts\python scraper\build.py          # scrape all sites, then build docs/data/suits.json
```

`scraper/build.py scrape <site>` re-scrapes one site; `scraper/build.py build` only re-filters.
Pages are cached in `scraper/.cache/` for 20 hours, so re-runs on the same day are quick. The
scraper waits one second between requests to each site.

Filters applied in `build.py`: stitched only (no unstitched / semi-stitched / dress material),
pieces ≤ 3, ₹1000–2000 per piece, in stock where the site's stock flag is reliable, not
described as print-only, and the same catalog listed on several sites is merged (cheapest
in-stock listing wins; the others appear as "Also sold on").
