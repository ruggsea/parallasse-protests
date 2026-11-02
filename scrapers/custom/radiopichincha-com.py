#!/usr/bin/env python3
"""List Radio Pichincha (radiopichincha.com) article URLs published 2026-09-25..2026-10-25.

Route: WordPress REST API /wp-json/wp/v2/posts (robots.txt is permissive, no
Sitemap directive; /sitemap.xml is 404). The REST 'date' field is the local
Quito post_date (UTC-5, no DST), which matches the publication date shown on
article pages (verified newest post 2026-10-26T00:01:00 against /feed/).
Pagination: per_page=100, after/before with a 1-day margin each side, stop
when a page's oldest date is before the window.
"""
import json
import sys
import time
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scrapers"))
from polite_fetch import fetch

API = ("https://radiopichincha.com/wp-json/wp/v2/posts"
       "?per_page=100&_fields=date,link&after={after}&before={before}&page={page}")
WINDOW_START = date(2026, 9, 25)
WINDOW_END = date(2026, 10, 25)
OUT = Path("data/urls_custom/radiopichincha-com.tsv")

# 1-day margin each side: REST after/before use the local post_date column,
# so margins keep boundary-day posts in; the window filter below is exact.
AFTER = (datetime.combine(WINDOW_START - timedelta(days=1), datetime.min.time())).isoformat()
BEFORE = (datetime.combine(WINDOW_END + timedelta(days=1), datetime.max.time())).isoformat()


def main():
    entries = {}  # normalized url -> (date, original url)
    page = 1
    while page <= 20:
        url = API.format(after=AFTER, before=BEFORE, page=page)
        st, txt, _ = fetch(url)
        if st != 200 or not txt:
            print(f"page {page}: status {st}, retrying once", flush=True)
            time.sleep(5)
            st, txt, _ = fetch(url)
            if st != 200 or not txt:
                print(f"page {page}: giving up at status {st}", flush=True)
                break
        items = json.loads(txt)
        if not items:
            break
        dates = []
        for it in items:
            d = datetime.fromisoformat(it["date"])
            dates.append(d.date())
            if WINDOW_START <= d.date() <= WINDOW_END:
                key = it["link"].rstrip("/")
                if key not in entries:
                    entries[key] = (d.date(), it["link"])
        oldest = min(dates)
        newest = max(dates)
        print(f"page {page}: {len(items)} posts, {newest} .. {oldest}", flush=True)
        if oldest < WINDOW_START:
            break  # descending order: everything older is outside the window
        if len(items) < 100:
            break
        page += 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w") as f:
        for key in sorted(entries):
            d, u = entries[key]
            f.write(f"{u}\t{d.isoformat()}\n")

    by_day = Counter(d for d, _ in entries.values())
    print(f"wrote {len(entries)} unique URLs to {OUT}")
    for d in sorted(by_day):
        print(f"  {d}: {by_day[d]}")
    for target in (date(2026, 9, 30), date(2026, 10, 10), date(2026, 10, 20)):
        print(f"CHECK {target}: {by_day.get(target, 0)} URLs")


if __name__ == "__main__":
    main()
