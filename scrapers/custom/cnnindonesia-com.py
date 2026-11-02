#!/usr/bin/env python3
"""Scrape CNN Indonesia article URLs for 2026-09-25 to 2026-10-25.
Writes TSV with URL and publication date (YYYY-MM-DD) to
data/urls_custom/cnnindonesia-com.tsv.
Uses the site's news sitemaps (sitemap_news.xml) discovered via the
robots.txt sitemap index. All HTTP requests go through polite_fetch.
"""

import sys
import os
import datetime
import xml.etree.ElementTree as ET
from collections import Counter

# Ensure the scraper directory is on sys.path for polite_fetch
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
# Add the project's scrapers directory where polite_fetch lives
sys.path.insert(0, os.path.join(BASE_DIR, "scrapers"))
# Also keep the repo root in case other imports rely on it
sys.path.insert(1, BASE_DIR)
try:
    from polite_fetch import fetch
except ImportError:
    sys.exit("polite_fetch not found – ensure this script runs from the project root")

START_DATE = datetime.date(2026, 9, 25)
END_DATE = datetime.date(2026, 10, 25)

NAMESPACE = {
    "sm": "http://www.sitemaps.org/schemas/sitemap/0.9",
    "news": "http://www.google.com/schemas/sitemap-news/0.9",
}

def iso_to_date(iso_str: str) -> datetime.date:
    """Convert ISO datetime with optional timezone to a date object."""
    # Strip timezone offset if present
    if "+" in iso_str:
        iso_str = iso_str.split("+")[0]
    if "-" in iso_str and iso_str.count("-") > 2:
        # e.g. 2026-10-26T06:18:29-07:00 – split at the last -
        iso_str = iso_str.rsplit("-", 1)[0]
    return datetime.datetime.fromisoformat(iso_str).date()

def parse_sitemap(url: str):
    """Fetch a sitemap (news or generic) and yield (url, date) tuples within the window.
    For news sitemaps we prefer the <news:publication_date>. For generic sitemaps we
    infer the date from the URL pattern YYYYMMDDxxxx where possible.
    """
    status, text, _ = fetch(url)
    if status != 200:
        return []
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return []
    entries = []
    for url_el in root.findall("sm:url", NAMESPACE):
        loc_el = url_el.find("sm:loc", NAMESPACE)
        if loc_el is None:
            continue
        article_url = loc_el.text.strip()
        # Try news:publication_date first
        pub_el = url_el.find("news:news/news:publication_date", NAMESPACE)
        pub_date = None
        if pub_el is not None and pub_el.text:
            try:
                pub_date = iso_to_date(pub_el.text.strip())
            except Exception:
                pub_date = None
        # Fallback: extract date from URL using the first 8‑digit segment
        if pub_date is None:
            import re
            m = re.search(r"/(\d{8})", article_url)
            if m:
                try:
                    pub_date = datetime.datetime.strptime(m.group(1), "%Y%m%d").date()
                except Exception:
                    pub_date = None
        if pub_date is None:
            continue
        if START_DATE <= pub_date <= END_DATE:
            entries.append((article_url, pub_date.isoformat()))
    return entries

def main():
    index_url = "https://www.cnnindonesia.com/sitemap.xml"
    status, text, _ = fetch(index_url)
    if status != 200:
        print(f"Failed to fetch sitemap index ({status})", file=sys.stderr)
        return
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        print(f"Failed to parse sitemap index: {e}", file=sys.stderr)
        return
    # collect sitemap URLs (news and regular web). Skip video sitemaps.
    sitemap_urls = []
    for sm_el in root.findall("sm:sitemap", NAMESPACE):
        loc_el = sm_el.find("sm:loc", NAMESPACE)
        if loc_el is None:
            continue
        loc = loc_el.text.strip()
        # Prefer news sitemaps but also include generic web sitemaps for older dates.
        if "sitemap_video" in loc:
            continue
        if loc.endswith('.xml'):
            sitemap_urls.append(loc)
    # Aggregate results, deduplicate by URL (keep first date encountered)
    results = {}
    for sm in sitemap_urls:
        for url, date in parse_sitemap(sm):
            if url not in results:
                results[url] = date
    # If we still lack enough URLs for any day, fall back to the Wayback CDX API
    def need_more():
        # simple heuristic: check if any day has fewer than 15 URLs
        for d, c in Counter(results.values()).items():
            if c < 15:
                return True
        return False
    if need_more():
        # Try Wayback CDX first (may be blocked), then RSS as a secondary source.
        cdx_url = (
            "https://web.archive.org/cdx/search/cdx?url=www.cnnindonesia.com/*"
            f"&from={START_DATE.strftime('%Y%m%d')}&to={END_DATE.strftime('%Y%m%d')}"
            "&output=json&collapse=urlkey"
        )
        status, text, _ = fetch(cdx_url)
        if status == 200 and text:
            import json
            try:
                rows = json.loads(text)
                for row in rows[1:]:
                    url = row[2]
                    timestamp = row[1]
                    try:
                        pub_date = datetime.datetime.strptime(timestamp[:8], "%Y%m%d").date()
                    except Exception:
                        continue
                    if START_DATE <= pub_date <= END_DATE and url not in results:
                        results[url] = pub_date.isoformat()
            except Exception:
                pass
        # RSS fallback
        rss_url = "https://www.cnnindonesia.com/rss"
        status, rss_text, _ = fetch(rss_url)
        if status == 200 and rss_text:
            import xml.etree.ElementTree as rssET
            try:
                rss_root = rssET.fromstring(rss_text)
                for item in rss_root.findall('.//item'):
                    guid_el = item.find('guid')
                    pub_el = item.find('pubDate')
                    if guid_el is None or pub_el is None:
                        continue
                    url = guid_el.text.strip()
                    # Parse pubDate, e.g., 'Mon, 26 Oct 2026 07:05:31 +0700'
                    try:
                        pub_dt = datetime.datetime.strptime(pub_el.text.strip(), "%a, %d %b %Y %H:%M:%S %z")
                        pub_date = pub_dt.date()
                    except Exception:
                        continue
                    if START_DATE <= pub_date <= END_DATE and url not in results:
                        results[url] = pub_date.isoformat()
            except Exception:
                pass
    # Write TSV sorted by date then URL
    out_path = os.path.abspath(os.path.join(BASE_DIR, "data", "urls_custom", "cnnindonesia-com.tsv"))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as out_f:
        for url, date in sorted(results.items(), key=lambda kv: (kv[1], kv[0])):
            out_f.write(f"{url}\t{date}\n")
    # Print per‑day counts
    counts = Counter(results.values())
    for day in sorted(counts):
        print(f"{day}\t{counts[day]}")
if __name__ == "__main__":
    main()
