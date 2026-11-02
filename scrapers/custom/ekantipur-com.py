#!/usr/bin/env python3
"""Kantipur (ekantipur.com) URL list for 2026-09-25..2026-10-25.

Route: robots.txt (200, no Disallow/Sitemap rules) -> homepage links
/sitemap_index -> 500 shards /sitemap_index/newsdetail/N. Shards are newest
first; each is a Google-News urlset of ~1000 <loc>s, each with
<news:publication_date> (Nepal local +05:45). Walk shards down from 1 until a
shard's oldest publication_date predates the window start; keep rows whose
date falls in the window. The publication_date date-part equals the
/YYYY/MM/DD/ segment of the URL and the page JSON-LD datePublished (verified
on samples), so it is the listed date. English variants (/en/ in the URL,
same article) are dropped so each article is listed once.
"""
import re
import sys
from datetime import date, datetime

sys.path.insert(0, "scrapers")
from polite_fetch import fetch

START = date(2026, 9, 25)
END = date(2026, 10, 25)
OUT = "data/urls_custom/ekantipur-com.tsv"

ROW_RE = re.compile(
    r"<loc>([^<]+)</loc><news:news><news:publication>"
    r"<news:name>[^<]*</news:name><news:language>[^<]*</news:language></news:publication>"
    r"<news:publication_date>([^<]+)</news:publication_date>"
)


def parse_shard(n):
    url = f"https://ekantipur.com/sitemap_index/newsdetail/{n}"
    st, text, _ = fetch(url)
    if st != 200 or not text:
        return st, []
    rows = []
    for loc, pub in ROW_RE.findall(text):
        if "/en/" in loc:
            continue  # English variant of the same article; list each article once
        try:
            d = datetime.fromisoformat(pub).date()
        except ValueError:
            continue
        rows.append((d, loc))
    return st, rows


def main():
    found = {}  # url -> date
    stop = False
    n = 1
    max_shard = 60
    while n <= max_shard and not stop:
        st, rows = parse_shard(n)
        if st != 200:
            print(f"shard {n}: HTTP {st}, stopping walk", file=sys.stderr)
            stop = True
        elif not rows:
            # empty or legacy shard (shard 200+ returned 200 with no urls)
            stop = True
        else:
            oldest = min(d for d, _ in rows)
            newest = max(d for d, _ in rows)
            print(f"shard {n}: {len(rows)} urls, {oldest}..{newest}")
            for d, loc in rows:
                if START <= d <= END:
                    found.setdefault(loc, d)
            if oldest < START:
                stop = True
        n += 1

    lines = []
    for loc in sorted(found, key=lambda u: (found[u], u)):
        lines.append(f"{loc}\t{found[loc].isoformat()}")
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    by_day = {}
    for d in found.values():
        by_day[d] = by_day.get(d, 0) + 1
    print(f"wrote {len(lines)} urls to {OUT}")
    for d in sorted(by_day):
        if START <= d <= END:
            print(f"{d.isoformat()}: {by_day[d]}")


if __name__ == "__main__":
    main()
