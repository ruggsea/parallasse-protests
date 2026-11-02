#!/usr/bin/env python3
"""List zf.ro article URLs published 2026-09-25..2026-10-25 -> data/urls_custom/zf-ro.tsv.

Route: /rss?page=N (20 items/page). The news sitemap (sitemap.xml) only covers ~2 days,
and siteindex.xml is a 2001-2004 relic, so the paginated RSS feed is the way back in time.
Dates: feed <pubDate> is UTC; converted to Europe/Bucharest (UTC+3, no DST in the window),
which is the date the site displays on each article page.
"""
import re
import sys
import email.utils
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, "scrapers")
from polite_fetch import fetch

ROOT = Path(__file__).resolve().parent.parent.parent
OUT = ROOT / "data/urls_custom/zf-ro.tsv"
START, END = "2026-09-25", "2026-10-25"
EET = timezone(timedelta(hours=3))
MAX_PAGES = 400

def main():
    articles = {}  # url -> date str
    stopped = "max pages"
    for page in range(1, MAX_PAGES + 1):
        url = f"https://www.zf.ro/rss?page={page}"
        st, tx, _ = fetch(url)
        if st != 200 or not tx:
            print(f"page {page}: status {st}, stopping")
            stopped = f"stopped at page {page} (status {st})"
            break
        items = re.findall(r"<item>(.*?)</item>", tx, re.S)
        if not items:
            print(f"page {page}: no items, stopping")
            stopped = f"stopped at page {page} (empty)"
            break
        oldest_local = None
        for it in items:
            m = re.search(r"<link>\s*(.*?)\s*</link>", it, re.S)
            d = re.search(r"<pubDate>\s*(.*?)\s*</pubDate>", it, re.S)
            if not m or not d:
                continue
            a_url = m.group(1).strip()
            dt = email.utils.parsedate_to_datetime(d.group(1))
            local = dt.astimezone(EET)
            dstr = local.date().isoformat()
            oldest_local = local if oldest_local is None or local < oldest_local else oldest_local
            if START <= dstr <= END and a_url not in articles:
                articles[a_url] = dstr
        print(f"page {page}: {len(items)} items, oldest {oldest_local.date()}, total in window {len(articles)}")
        if oldest_local and oldest_local.date().isoformat() < START:
            stopped = f"reached pre-window at page {page}"
            break
    OUT.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(OUT, "w") as f:
        for u in sorted(articles):
            f.write(f"{u}\t{articles[u]}\n")
            n += 1
    # per-day counts
    per = {}
    for d in articles.values():
        per[d] = per.get(d, 0) + 1
    print(f"\nwrote {n} URLs to {OUT} ({stopped})")
    for d in sorted(per):
        print(d, per[d])
    missing = [d for d in (START, "2026-09-30", "2026-10-10", "2026-10-20", END) if per.get(d, 0) < 15]
    if missing:
        print("WARNING thin days:", missing)

if __name__ == "__main__":
    main()
