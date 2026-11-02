#!/usr/bin/env python3
"""List sicnoticias.pt (SIC Noticias, Portugal) article URLs published 2026-09-25..2026-10-25.

Route (verified 2026-10-26): robots.txt (200) is permissive for "*" (disallows only
/api, /sites, /sandbox, /sandbox2013, /pesquisa, /hotfolder-video-exports) and names
https://sicnoticias.pt/sitemap/index.xml. That index is a per-DAY sitemap:
https://sicnoticias.pt/sitemap/YYYY/MM/YYYY-MM-DD.xml for every day (1378 files back
to 2022-10; all 31 files of the window exist, index 200). Each day file is a flat
urlset (300-400 urls) where every <loc> carries the publication date in its own
URL path: https://sicnoticias.pt/<section>/YYYY-MM-DD-<slug>-<hash>. The path date
is the date the site states (same-day grouping in the day file, and it matches
news:publication_date in the Google News sitemap /sitemap/news.xml to the day for
the overwhelming majority of items; a handful of late-night items, UTC pub time
23:00-23:45, are path-dated the next day, always <=1 day apart).

CAVEAT (recorded, not hideable): every non-sitemap page on sicnoticias.pt
(homepage, section pages, article pages, ?amp=1, /amp/, www variant) returns 403
to the ParallasseResearchBot UA -- 66 persistent 403s in the shared fetch log
across 2026-10-25 and 2026-10-26, not a transient WAF. Only robots.txt and
/sitemap/* return 200. So dates below come from the sitemap URL structure (the
site's own stated date), and sample page dates were verified through
web.archive.org snapshots (JSON-LD datePublished) because the live pages cannot
be fetched by this bot at all.
"""
import re
import sys
import time
import datetime as dt
from pathlib import Path

sys.path.insert(0, "scrapers")
from polite_fetch import fetch

START, END = "2026-09-25", "2026-10-25"
OUT = Path("data/urls_custom/sicnoticias-pt.tsv")
DATE_RE = re.compile(r"/(\d{4}-\d{2}-\d{2})-")
LOC_RE = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>")


def main():
    seen = {}
    d = dt.date.fromisoformat(START)
    end = dt.date.fromisoformat(END)
    missing = []
    while d <= end:
        url = f"https://sicnoticias.pt/sitemap/{d.year}/{d.month:02d}/{d.isoformat()}.xml"
        text, status = None, None
        for attempt in range(3):
            status, text, _ = fetch(url)
            if status == 200 and text:
                break
            time.sleep(3 * (attempt + 1))
        if status != 200 or not text:
            missing.append((d.isoformat(), status))
            d += dt.timedelta(days=1)
            continue
        for u in LOC_RE.findall(text):
            if not u.startswith("https://"):
                continue
            m = DATE_RE.search(u)
            if not m:
                continue
            pub = m.group(1)
            if not (START <= pub <= END):
                continue
            if u not in seen:
                seen[u] = pub
        d += dt.timedelta(days=1)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    rows = sorted(seen.items(), key=lambda kv: (kv[1], kv[0]))
    with OUT.open("w", encoding="utf-8") as f:
        for u, pub in rows:
            f.write(f"{u}\t{pub}\n")

    per_day = {}
    for _, pub in rows:
        per_day[pub] = per_day.get(pub, 0) + 1
    for day in sorted(per_day):
        print(f"{day}: {per_day[day]}")
    print(f"TOTAL {len(rows)} urls, {len(per_day)} days")
    if missing:
        print("MISSING day files:", missing, file=sys.stderr)


if __name__ == "__main__":
    main()
