#!/usr/bin/env python3
"""Scrape article URLs from rm.id (Rakyat Merdeka) for the period 2026-09-25 to 2026-10-25.
It attempts the following routes, in order, using the polite_fetch helper which respects
robots.txt, handles Cloudflare challenges, and rate‑limits per host:
1. Sitemap(s) listed in /sitemap.xml (or sitemap index). URLs are taken with their <lastmod>
   date when present.
2. Per‑day archive pages ``https://rm.id/YYYY/MM/DD/`` – the page normally lists article
   links; the archive date is used as the publication date.
3. As a last resort, the Internet Archive CDX API is queried (if reachable) and the
   returned timestamps are used.
All collected URLs are de‑duplicated, filtered to the target window, and written to
``data/urls_custom/rm-id.tsv`` as ``URL<TAB>YYYY-MM-DD`` (no header). The script prints a
summary of how many URLs were written per day.
"""

import sys
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from collections import defaultdict

# Ensure the helper module can be imported (relative to the repo root)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
# The repository provides a small wrapper for fetching with Cloudflare handling.
# It is located at ``scrapers/polite_fetch.py`` – we import the ``fetch`` function.
try:
    from polite_fetch import fetch
except Exception as e:
    print("Error importing polite_fetch:", e)
    sys.exit(1)

START = datetime(2026, 9, 25)
END = datetime(2026, 10, 25)
BASE = "https://rm.id"
OUTPUT_TSV = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/urls_custom/rm-id.tsv"))

def iso_date(s: str) -> str:
    """Return YYYY-MM-DD from an ISO‑like datetime string (or None)."""
    try:
        dt = datetime.fromisoformat(s.rstrip('Z'))
        return dt.strftime('%Y-%m-%d')
    except Exception:
        return None

def fetch_sitemap(url: str, collected: dict):
    """Recursively fetch sitemap or sitemap index and fill *collected*.
    ``collected`` maps URL -> date string (YYYY‑MM‑DD) taken from <lastmod> if present.
    """
    status, text, _ = fetch(url)
    if status != 200:
        print(f"[sitemap] failed {url} -> {status}")
        return
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        print(f"[sitemap] XML parse error {url}: {e}")
        return
    ns = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9',
          'news': 'http://www.google.com/schemas/sitemap-news/0.9'}
    # Detect if this is a sitemapindex
    if root.tag.endswith('sitemapindex'):
        for sm in root.findall('sm:sitemap', ns):
            loc = sm.find('sm:loc', ns)
            if loc is not None and loc.text:
                fetch_sitemap(loc.text.strip(), collected)
        return
    # Otherwise it's a urlset
    for url_el in root.findall('sm:url', ns):
        loc_el = url_el.find('sm:loc', ns)
        if loc_el is None or not loc_el.text:
            continue
        url_val = loc_el.text.strip()
        # Prefer <news:publication_date> if present, else <lastmod>
        date_str = None
        news_pub = url_el.find('news:news', ns)
        if news_pub is not None:
            pub_date_el = news_pub.find('news:publication_date', ns)
            if pub_date_el is not None and pub_date_el.text:
                date_str = iso_date(pub_date_el.text.strip())
        if not date_str:
            lastmod_el = url_el.find('sm:lastmod', ns)
            if lastmod_el is not None and lastmod_el.text:
                date_str = iso_date(lastmod_el.text.strip())
        if date_str:
            collected[url_val] = date_str
        else:
            # keep without date – we may try to infer later
            collected[url_val] = None

def scrape_archive_pages(collected: dict):
    """Iterate over each day in the target window and scrape ``BASE/YYYY/MM/DD/``.
    Any discovered article links are added with the archive date.
    """
    cur = START
    while cur <= END:
        archive_url = f"{BASE}/{cur.strftime('%Y/%m/%d/') }"
        status, text, _ = fetch(archive_url)
        if status == 200:
            # simple href extraction – look for URLs that contain the domain and a /baca-berita/ path
            links = re.findall(r'href=[\"\'](https?://[^\"\']+)[\"\']', text)
            for link in links:
                if 'rm.id' in link and '/baca-berita/' in link:
                    if link not in collected:
                        collected[link] = cur.strftime('%Y-%m-%d')
        else:
            # silently ignore missing archive pages
            pass
        cur += timedelta(days=1)

def fallback_wayback(collected: dict):
    """Query the Wayback CDX API for any missing URLs.
    Only adds entries that are still within the window.
    """
    api = (
        "https://web.archive.org/cdx/search/cdx?url=rm.id/*"
        f"&from={START.strftime('%Y%m%d')}&to={END.strftime('%Y%m%d')}&output=json&collapse=urlkey"
    )
    status, text, _ = fetch(api)
    if status != 200:
        print(f"[wayback] request failed {status}")
        return
    try:
        import json
        rows = json.loads(text)
    except Exception as e:
        print(f"[wayback] json parse error: {e}")
        return
    # rows[0] is header, format: ["urlkey","timestamp",...]
    for row in rows[1:]:
        url = row[0]
        ts = row[1]
        try:
            dt = datetime.strptime(ts, "%Y%m%d%H%M%S")
            date_str = dt.strftime('%Y-%m-%d')
        except Exception:
            continue
        if START.strftime('%Y-%m-%d') <= date_str <= END.strftime('%Y-%m-%d'):
            if url not in collected:
                collected[url] = date_str

def main():
    collected = {}
    # 1. Try sitemap
    fetch_sitemap(f"{BASE}/sitemap.xml", collected)
    # 2. Archive pages
    scrape_archive_pages(collected)
    # 3. Wayback fallback for any missing
    fallback_wayback(collected)

    # Filter to the date window and drop entries with unknown date
    final = {u: d for u, d in collected.items() if d and START <= datetime.strptime(d, '%Y-%m-%d') <= END}

    # De‑duplicate – dict keys are unique already
    # Write TSV sorted by date then URL
    os.makedirs(os.path.dirname(OUTPUT_TSV), exist_ok=True)
    with open(OUTPUT_TSV, "w", encoding="utf-8") as f:
        for url, date in sorted(final.items(), key=lambda x: (x[1], x[0])):
            f.write(f"{url}\t{date}\n")

    # Print per‑day counts
    per_day = defaultdict(int)
    for d in final.values():
        per_day[d] += 1
    for d in sorted(per_day):
        print(f"{d}\t{per_day[d]}")

if __name__ == "__main__":
    main()
