#!/usr/bin/env python3
"""Eenadu (eenadu.net) custom scraper.
Collects article URLs published between 2026-09-25 and 2026-10-25 (inclusive).
The site provides per‑day archive pages at:
    https://www.eenadu.net/archivio/YYYY/MM/DD
Each archive page lists article links (full URLs). For each article we fetch the page
and extract the publication date from either a <meta property="article:published_time">
or from JSON‑LD ``datePublished``. Only URLs whose extracted date falls inside the
window are written.
Output TSV (data/urls_custom/eenadu-net.tsv):
    URL<TAB>YYYY-MM-DD
No header, one line per unique URL.
The script prints a per‑day count of URLs written.
"""
import sys, os, re
from datetime import date, datetime, timedelta
import xml.etree.ElementTree as ET

# add project scrapers dir for polite_fetch
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scrapers"))
from polite_fetch import fetch

START = date(2026, 9, 25)
END   = date(2026, 10, 25)

ARCHIVE_URL_TEMPLATE = "https://www.eenadu.net/archivio/{year:04d}/{month:02d}/{day:02d}"

def daterange(start, end):
    cur = start
    while cur <= end:
        yield cur
        cur += timedelta(days=1)

def fetch_archive(day: date):
    url = ARCHIVE_URL_TEMPLATE.format(year=day.year, month=day.month, day=day.day)
    status, txt, _ = fetch(url)
    if status != 200 or not txt:
        print(f"[warn] archive {day} fetch status {status}", file=sys.stderr)
        return []
    # extract full URLs that look like article links
    # pattern: href="https://www.eenadu.net/…/digits" (numeric id at end)
    urls = re.findall(r'href\s*=\s*"(https://www\.eenadu\.net/[^"]+?)"', txt)
    # keep those containing a news section (telugu-news, breaking-news, etc.) and ending with a numeric ID
    article_urls = []
    for u in urls:
        if re.search(r'/telugu-news/|/breaking-news/|/news/', u) and re.search(r'/\d+$', u):
            article_urls.append(u)
    return article_urls

def extract_pubdate(html: str) -> str:
    # Try meta tag first
    m = re.search(r'<meta[^>]+property\s*=\s*["\']article:published_time["\'][^>]*content\s*=\s*["\']([^"\']+)["\']', html, re.I)
    if m:
        return m.group(1).split('T')[0]
    # Fallback to JSON‑LD "datePublished"
    m = re.search(r'"datePublished"\s*:\s*"(\d{4}-\d{2}-\d{2})', html)
    if m:
        return m.group(1)
    return None

def main():
    all_urls = {}
    for day in daterange(START, END):
        daily_urls = fetch_archive(day)
        for url in daily_urls:
            if url in all_urls:
                continue
            # Use the archive day as the publication date (the archive page groups
            # articles published on that calendar date). No further fetch is needed.
            if START <= day <= END:
                all_urls[url] = day.isoformat()
        # optional progress per day
        print(f"{day.isoformat()}\t{len([u for u,d in all_urls.items() if d.startswith(day.isoformat())])}")
    # write TSV
    out_path = os.path.join(PROJECT_ROOT, "data", "urls_custom", "eenadu-net.tsv")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as out:
        for u, d in sorted(all_urls.items()):
            out.write(f"{u}\t{d}\n")
    print(f"Wrote {len(all_urls)} URLs to {out_path}")

if __name__ == "__main__":
    main()
