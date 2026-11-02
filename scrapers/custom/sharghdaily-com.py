#!/usr/bin/env python3
"""Shargh Daily (sharghdaily.com) — article URLs published 2026-09-25 .. 2026-10-25.

Route (verified 2026-10-26):
- robots.txt is permissive and names https://www.sharghdaily.com/sitemap.xml.
- The index lists per-day sitemaps whose filename is the base64 of
  {"model":"newsstudioDateRange","date":"YYYY-MM-DD"} — one URLSET per day.
- Each day's file lists exactly that day's articles; <lastmod> is the
  publication time (== page JSON-LD datePublished to the second, verified on
  post 1135959: sitemap 2026-10-20T00:30:00+00:00 == page 2026-10-20T00:30:00Z).
- <loc> values contain raw Persian (non-ASCII) characters. Fetching them
  unencoded fails instantly (status 0: http.client cannot put them in the
  request line), which is why earlier attempts scored 0/6 samples.
  Percent-encoding the path fixes it (status 200, 157 KB page).
- /video/ URLs are skipped (video pages, not articles).

Output: data/urls_custom/sharghdaily-com.tsv  —  URL<TAB>YYYY-MM-DD, unique.
"""
import base64
import datetime
import json
import re
import sys
import urllib.parse

sys.path.insert(0, "scrapers")
from polite_fetch import fetch

BASE = "https://www.sharghdaily.com"
START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)
OUT = "data/urls_custom/sharghdaily-com.tsv"


def enc_url(raw):
    """Percent-encode the path so the request line is pure ASCII."""
    p = urllib.parse.urlsplit(raw.strip())
    return urllib.parse.urlunsplit(
        (p.scheme, p.netloc, urllib.parse.quote(p.path, safe="/"), p.query, p.fragment)
    )


def day_sitemap_url(day):
    payload = json.dumps(
        {"model": "newsstudioDateRange", "date": day.isoformat()},
        separators=(",", ":"),
    ).encode()
    b64 = base64.b64encode(payload).decode()
    return f"{BASE}/sitemap/{b64}.xml"


def main():
    items = {}  # encoded url -> listed date; first (oldest) day wins
    missing = []
    d = START
    while d <= END:
        status, text, path = fetch(day_sitemap_url(d))
        if status != 200 or not text:
            missing.append((d.isoformat(), status))
            d += datetime.timedelta(days=1)
            continue
        found = 0
        for loc, lm in re.findall(r"<loc>(.*?)</loc>\s*<lastmod>(.*?)</lastmod>", text, re.S):
            loc = loc.strip()
            if not loc.startswith(BASE + "/") or "/video/" in loc:
                continue
            lm_date = lm.strip()[:10]
            if not (START.isoformat() <= lm_date <= END.isoformat()):
                continue
            u = enc_url(loc)
            if u not in items:
                items[u] = lm_date
                found += 1
        print(f"{d.isoformat():14} urls added: {found}")
        d += datetime.timedelta(days=1)

    if missing:
        print("MISSING sitemaps:", missing, file=sys.stderr)

    rows = sorted(items.items(), key=lambda kv: (kv[1], kv[0]))
    with open(OUT, "w", encoding="utf-8") as f:
        for url, date in rows:
            f.write(f"{url}\t{date}\n")

    per_day = {}
    for _, date in rows:
        per_day[date] = per_day.get(date, 0) + 1
    print(f"WROTE {len(rows)} unique URLs to {OUT}")
    for day in sorted(per_day):
        print(f"  {day}: {per_day[day]}")
    for key in ("2026-09-30", "2026-10-10", "2026-10-20"):
        print(f"CHECK {key}: {per_day.get(key, 0)} urls (need >= 15)")


if __name__ == "__main__":
    main()
