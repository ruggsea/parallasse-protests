#!/usr/bin/env python3
"""gogo.mn (Mongolia) article URL lister for 2026-09-25 .. 2026-10-25.

Route: the site is a Next.js app whose own front-end calls the public JSON API
    https://backend.gogo.mn/api/v1/news/list?page=N&limit=100
(the endpoint was read out of the site's own JS chunk: useLatestNews -> "/news/list?page=&limit=").
Each item carries `lid` (the short id used in the article URL https://gogo.mn/r/<lid>)
and `publishDate` (ISO UTC, equal to the page's JSON-LD NewsArticle datePublished).
robots.txt on gogo.mn allows everything but /preview/; backend.gogo.mn has no robots.txt (404 -> open).

Output: data/urls_custom/gogo-mn.tsv, "URL<TAB>YYYY-MM-DD", no header, unique URLs.
"""
import json
import os
import sys
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scrapers"))
from polite_fetch import fetch  # noqa: E402

API = "https://backend.gogo.mn/api/v1/news/list"
START = date(2026, 9, 25)
END = date(2026, 10, 25)
OUT = ROOT / "data/urls_custom/gogo-mn.tsv"
MIN_WORDS = int(os.environ.get("GOGO_MIN_WORDS", "0"))
MAX_PAGES = int(os.environ.get("GOGO_MAX_PAGES", "60"))


def get_json(url, tries=3):
    for i in range(tries):
        st, tx, _ = fetch(url)
        if st == 200 and tx:
            try:
                return json.loads(tx)
            except ValueError:
                pass
        print(f"  retry {i + 1} {url} status={st}", file=sys.stderr)
    return None


def main():
    rows = {}
    stats = Counter()
    page = 1
    stop = False
    while page <= MAX_PAGES and not stop:
        url = f"{API}?page={page}&limit=100"
        d = get_json(url)
        if not d or not d.get("data") or not d["data"].get("items"):
            print(f"page {page}: no data, stopping", file=sys.stderr)
            break
        items = d["data"]["items"]
        oldest = None
        for it in items:
            lid = it.get("lid")
            pd = it.get("publishDate")
            if not lid or not pd:
                continue
            try:
                dt = datetime.strptime(pd[:19], "%Y-%m-%dT%H:%M:%S")
            except ValueError:
                continue
            day = dt.date()
            oldest = day if oldest is None or day < oldest else oldest
            if not (START <= day <= END):
                continue
            wc = it.get("wordCount")
            if MIN_WORDS and isinstance(wc, int) and wc < MIN_WORDS:
                stats["skipped_short"] += 1
                continue
            u = f"https://gogo.mn/r/{lid}"
            rows.setdefault(u, day.isoformat())
        print(f"page {page}: {len(items)} items, oldest {oldest}", file=sys.stderr)
        if oldest is not None and oldest < START - timedelta(days=2):
            stop = True
        page += 1

    per_day = Counter(rows.values())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w") as f:
        for u in sorted(rows, key=lambda k: (rows[k], k), reverse=True):
            f.write(f"{u}\t{rows[u]}\n")
    print(f"wrote {len(rows)} urls to {OUT}")
    d0 = START
    while d0 <= END:
        print(f"  {d0.isoformat()}\t{per_day.get(d0.isoformat(), 0)}")
        d0 += timedelta(days=1)
    for k, v in stats.items():
        print(f"  {k}\t{v}")


if __name__ == "__main__":
    main()
