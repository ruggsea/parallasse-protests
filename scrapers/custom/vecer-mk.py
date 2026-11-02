#!/usr/bin/env python3
"""vecer.mk (North Macedonia) article URL list, 2026-09-25 .. 2026-10-25.

Route: the site's own paginated list API, /api/articles?category=X&page=N
(the endpoint its Alpine.js "load more" button calls). Returns an HTML
fragment of 20 article cards per page, each card carrying the displayed
publication date (DD-MM-YYYY) next to the clock icon. Pages are sorted
newest-first, so we stop a category once a page's oldest date predates the
window. The RSS feed (/feed/) is used only for URLs the category API never
returned (e.g. cross-listed items), with the feed's pubDate day.

Output: data/urls_custom/vecer-mk.tsv  lines: URL<TAB>YYYY-MM-DD, unique.
"""
import re
import sys
import email.utils
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, "scrapers")
from polite_fetch import fetch

BASE = "https://vecer.mk"
CATS = ["makedonija", "balkan", "svet", "life", "zabavna", "ekonomija",
        "kujna", "komentari-i-analizi", "skopska", "cult", "sport"]
WIN_START = date(2026, 9, 25)
WIN_END = date(2026, 10, 25)
ROOT = Path(".")
OUT = ROOT / "data/urls_custom" / "vecer-mk.tsv"
MAX_PAGES = 80  # safety cap per category


def parse_ddmmyy(s):
    try:
        d, m, y = s.split("-")
        return date(int(y), int(m), int(d))
    except (ValueError, AttributeError):
        return None


def cards(text):
    """Yield (url, date) per article card in an API HTML fragment."""
    blocks = re.split(r'(?=<a href="/[a-z0-9\-]+/)', text or "")
    out = []
    for b in blocks[1:]:
        m = re.match(r'<a href="([^"]+)"', b)
        d = re.search(r'>\s*(\d{1,2}-\d{1,2}-\d{4})\s*<', b)
        if not m:
            continue
        url = m.group(1).split("?")[0]
        if url.startswith("/"):
            url = BASE + url
        dt = parse_ddmmyy(d.group(1)) if d else None
        if dt:
            out.append((url, dt))
    return out


def main():
    found = {}  # url -> date (first listing wins; card date is exact)

    for cat in CATS:
        got = 0
        for page in range(1, MAX_PAGES + 1):
            url = f"{BASE}/api/articles?category={cat}&page={page}"
            status, text, _ = fetch(url)
            if status != 200:
                print(f"  {cat} p{page}: HTTP {status}, stopping category")
                break
            cs = cards(text)
            if not cs:
                print(f"  {cat} p{page}: no cards, stopping category")
                break
            dates = [dt for _, dt in cs]
            for u, dt in cs:
                if WIN_START <= dt <= WIN_END:
                    found.setdefault(u, dt)
                    got += 1
            if min(dates) < WIN_START:
                print(f"  {cat} p{page}: oldest {min(dates)}, before window, stopping")
                break
            if len(cs) < 20:
                print(f"  {cat} p{page}: short page ({len(cs)}), category exhausted")
                break
            if page % 10 == 0:
                print(f"  {cat} p{page}: {got} so far")
        print(f"{cat}: +{got} urls in window")

    # RSS fallback for anything the category API missed
    status, text, _ = fetch(f"{BASE}/feed/")
    rss_added = 0
    if status == 200:
        items = re.findall(r"<item>.*?</item>", text or "", re.S)
        for it in items:
            lm = re.search(r"<link>(.*?)</link>", it, re.S)
            pm = re.search(r"<pubDate>(.*?)</pubDate>", it, re.S)
            if not (lm and pm):
                continue
            u = lm.group(1).strip()
            if u in found:
                continue
            try:
                dt = email.utils.parsedate_to_datetime(pm.group(1).strip()).date()
            except (ValueError, TypeError):
                continue
            if WIN_START <= dt <= WIN_END:
                found[u] = dt
                rss_added += 1
    print(f"rss fallback: +{rss_added} urls")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    rows = sorted(found.items(), key=lambda kv: (kv[1], kv[0]))
    with OUT.open("w", encoding="utf-8") as f:
        for u, dt in rows:
            f.write(f"{u}\t{dt.isoformat()}\n")

    per_day = {}
    for _, dt in rows:
        per_day[dt] = per_day.get(dt, 0) + 1
    print(f"\nwrote {len(rows)} urls to {OUT}")
    for d in sorted(per_day):
        print(f"{d.isoformat()}\t{per_day[d]}")
    if len(rows) == 0:
        print("ERROR: no urls collected")
        sys.exit(1)


if __name__ == "__main__":
    main()
