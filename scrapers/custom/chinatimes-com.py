#!/usr/bin/env python3
"""Scrape China Times (chinatimes.com) article URLs between 2026-09-25 and 2026-10-25.
Writes TSV with URL<TAB>YYYY-MM-DD to data/urls_custom/chinatimes-com.tsv.
Uses polite_fetch to respect robots.txt and rate limits.
Falls back to Wayback CDX API if sitemaps are inaccessible.
"""

import sys, os, datetime, collections, json, xml.etree.ElementTree as ET

# make polite_fetch importable (project root is two levels up from this file)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from polite_fetch import fetch

START = datetime.date(2026, 9, 25)
END   = datetime.date(2026, 10, 25)

# Primary route: sitemap index listed in robots.txt
# Primary route: known sitemap URLs (not index files)
SITEMAP_URLS = [
    "https://www.chinatimes.com/sitemaps/sitemap_todaynews.xml",
    "https://www.chinatimes.com/sitemaps/sitemap_todaynews_d2.xml",
]

def fetch_url(url):
    status, text, _ = fetch(url)
    return status, text

def parse_sitemap(xml_text):
    ns = {
        'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9',
        'news': 'http://www.google.com/schemas/sitemap-news/0.9',
    }
    root = ET.fromstring(xml_text)
    entries = []
    for url_el in root.findall('sm:url', ns):
        loc_el = url_el.find('sm:loc', ns)
        if loc_el is None or not loc_el.text:
            continue
        url = loc_el.text.strip()
        date_el = url_el.find('news:news/news:publication_date', ns)
        if date_el is None:
            date_el = url_el.find('sm:lastmod', ns)
        if date_el is None or not date_el.text:
            continue
        date_text = date_el.text.strip()
        try:
            dt = datetime.datetime.fromisoformat(date_text)
        except Exception:
            try:
                dt = datetime.datetime.strptime(date_text[:10], "%Y-%m-%d")
            except Exception:
                continue
        pub_date = dt.date()
        if START <= pub_date <= END:
            entries.append((url, pub_date))
    return entries

def crawl_sitemaps():
    all_entries = []
    for sm_url in SITEMAP_URLS:
        status, txt = fetch_url(sm_url)
        if status != 200:
            continue
        try:
            all_entries.extend(parse_sitemap(txt))
        except Exception as e:
            print(f"Warning: could not process sitemap {sm_url}: {e}", file=sys.stderr)
    return all_entries

def cdx_fallback():
    # Wayback CDX API: collapse duplicate URLs, limit to our window
    cdx_url = (
        "https://webcache.googleusercontent.com/search?q=cache:web.archive.org/cdx/search/cdx?"  # placeholder, will be overridden
    )
    # Use direct Wayback CDX endpoint
    cdx_url = (
        f"https://web.archive.org/cdx/search/cdx?url=www.chinatimes.com/*&from=20260925&to=20261025&output=json&collapse=urlkey"
    )
    status, txt, _ = fetch(cdx_url)
    if status != 200:
        return []
    try:
        data = json.loads(txt)
    except Exception:
        return []
    # First line is header, subsequent lines are fields: url, timestamp, ...
    entries = []
    for row in data[1:]:
        url = row[0]
        ts = row[1]  # format YYYYMMDDhhmmss
        try:
            dt = datetime.datetime.strptime(ts, "%Y%m%d%H%M%S")
        except Exception:
            continue
        pub_date = dt.date()
        if START <= pub_date <= END:
            entries.append((url, pub_date))
    return entries

def write_tsv(pairs, out_path):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for url, date in sorted(pairs, key=lambda x: (x[1], x[0])):
            f.write(f"{url}\t{date.isoformat()}\n")

def main():
    entries = crawl_sitemaps()
    if not entries:
        # fallback to Wayback CDX if no entries gathered
        entries = cdx_fallback()
    # deduplicate, keep first date encountered
    uniq = {}
    for url, d in entries:
        if url not in uniq:
            uniq[url] = d
    pairs = [(u, d) for u, d in uniq.items()]
    out_file = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'chinatimes-com.tsv'))
    write_tsv(pairs, out_file)
    # report per‑day counts
    counter = collections.Counter(d for _, d in pairs)
    for day in sorted(counter):
        print(f"{day}: {counter[day]} URLs")
    print(f"Total URLs written: {len(pairs)}")

if __name__ == "__main__":
    main()
