#!/usr/bin/env python3
"""List divaina.lk article URLs published 2026-09-25..2026-10-25 (site-local +05:30).

Route: WP REST API /wp-json/wp/v2/posts (robots.txt permissive, allows everything
except /app/assets/, /wp-admin/, xmlrpc etc). 'date' field is the site-local
publication date (+05:30), which equals the page JSON-LD datePublished.
Do NOT use the sitemap <lastmod>: it is the last-edit time and can differ from
datePublished by up to a day (verified: sitemap lastmod 2026-10-11T14:30Z vs
page datePublished 2026-10-12T05:10+05:30 on /cartoons/107683).
Fallback if REST fails: post-sitemap29..32.xml (lastmod-based, imperfect).
"""
import sys, json, re, os
from pathlib import Path

sys.path.insert(0, "scrapers")
from polite_fetch import fetch

ROOT = Path(".")
OUT = ROOT / "data/urls_custom/divaina-lk.tsv"
WIN_START = "2026-09-25"
WIN_END = "2026-10-25"

def fetch_json(url):
    status, text, _ = fetch(url)
    if status != 200:
        return None, status
    return json.loads(text), status

def rest_route():
    """Paginate WP REST posts; return {url: local_date}."""
    found = {}
    page = 1
    while page <= 80:
        url = (
            "https://www.divaina.lk/wp-json/wp/v2/posts?per_page=100"
            "&_fields=link,date"
            "&after=2026-09-24T00:00:00&before=2026-10-26T00:00:00"
            f"&page={page}"
        )
        data, status = fetch_json(url)
        if data is None:
            print(f"REST page {page}: status {status}, aborting REST route")
            break
        if not data:
            break
        for item in data:
            found[item["link"]] = item["date"][:10]
        print(f"REST page {page}: {len(data)} items (total {len(found)})")
        if len(data) < 100:
            break
        page += 1
    return found

def sitemap_route():
    """Fallback: arnebrachhold post sitemaps 29-32 (ordered oldest->newest by lastmod).
    lastmod = last-edit time, so dates may drift up to ~1 day from datePublished."""
    found = {}
    for n in [29, 30, 31, 32]:
        url = f"https://www.divaina.lk/post-sitemap{n}.xml"
        status, text, _ = fetch(url)
        if status != 200 or not text:
            print(f"sitemap {n}: status {status}, skipped")
            continue
        pairs = re.findall(r"<loc>([^<]+)</loc>\s*(?:<lastmod>([^<]+)</lastmod>)?", text)
        for loc, lm in pairs:
            if lm:
                found[loc] = lm[:10]
        print(f"sitemap {n}: {len(pairs)} urls")
    return found

def main():
    found = rest_route()
    if len(found) < 100:
        print("REST route gave too little; trying sitemap fallback")
        found = sitemap_route()
    rows, seen = [], set()
    for url, d in found.items():
        if WIN_START <= d <= WIN_END and url not in seen:
            seen.add(url)
            rows.append((d, url))
    rows.sort()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w") as f:
        for d, url in rows:
            f.write(f"{url}\t{d}\n")
    per_day = {}
    for d, _ in rows:
        per_day[d] = per_day.get(d, 0) + 1
    print(f"WROTE {len(rows)} unique URLs to {OUT}")
    for d in sorted(per_day):
        print(f"{d}: {per_day[d]}")
    missing = [d for d in ("2026-09-30", "2026-10-10", "2026-10-20") if per_day.get(d, 0) < 15]
    if missing:
        print("WARNING: low counts on", missing)

if __name__ == "__main__":
    main()
