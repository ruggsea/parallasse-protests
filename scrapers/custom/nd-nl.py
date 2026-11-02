#!/usr/bin/env python3
"""Scrape article URLs from Nederlands Dagblad (nd.nl) for a given date range.
Uses the XML sitemap for recent items and falls back to paginated RSS feed
to cover older dates. All HTTP requests go through ``polite_fetch.fetch``
which respects robots.txt and rate‑limits.
"""
import sys, os, datetime
from collections import Counter

# Ensure ``polite_fetch`` is importable from the project root.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from polite_fetch import fetch
except ImportError:
    print('polite_fetch not found', file=sys.stderr)
    sys.exit(1)

# ----- Configuration -------------------------------------------------------
SITEMAP_URL = "https://www.nd.nl/xmlsitemap"
RSS_URL_TEMPLATE = "https://www.nd.nl/nieuws/rss?page={page}"
OUTPUT_TSV = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'nd-nl.tsv'))
START_DATE = datetime.date(2026, 9, 25)
END_DATE = datetime.date(2026, 10, 25)
MAX_RSS_PAGES = 500  # safety guard to avoid infinite loops

# ----- Helper functions ----------------------------------------------------
def fetch_text(url: str) -> str:
    """Fetch *url* with ``polite_fetch`` and return its text body.
    Exits on non‑200 HTTP status.
    """
    status, text, _ = fetch(url)
    if status != 200:
        raise RuntimeError(f"Failed to fetch {url}: HTTP {status}")
    return text

def parse_sitemap(xml_text: str):
    """Parse the XML sitemap and return ``[(url, date), …]`` within range."""
    import xml.etree.ElementTree as ET
    ns = {
        'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9',
        'news': 'http://www.google.com/schemas/sitemap-news/0.9',
    }
    root = ET.fromstring(xml_text)
    entries = []
    for url_el in root.findall('ns:url', ns):
        loc_el = url_el.find('ns:loc', ns)
        pub_el = url_el.find('news:news/news:publication_date', ns)
        if loc_el is None or pub_el is None:
            continue
        url = loc_el.text.strip()
        try:
            pub_date = datetime.datetime.fromisoformat(pub_el.text.strip()).date()
        except Exception:
            continue
        if START_DATE <= pub_date <= END_DATE:
            entries.append((url, pub_date))
    return entries

def parse_rss(rss_text: str):
    """Very lightweight RSS parser – extracts <guid> URL and <pubDate>."""
    entries = []
    items = rss_text.split('<item>')[1:]  # first split is header
    for item in items:
        try:
            # guid
            guid_start = item.index('<guid')
            guid_end = item.index('</guid>', guid_start)
            guid_part = item[guid_start:guid_end]
            url = guid_part.split('>')[1].strip()
            # pubDate
            pd_start = item.index('<pubDate>') + len('<pubDate>')
            pd_end = item.index('</pubDate>', pd_start)
            pub_str = item[pd_start:pd_end].strip()
            pub_date = datetime.datetime.strptime(pub_str, "%a, %d %b %Y %H:%M:%S %Z").date()
            if START_DATE <= pub_date <= END_DATE:
                entries.append((url, pub_date))
        except Exception:
            continue
    return entries

def collect_entries():
    """Gather entries from sitemap first, then paginate RSS until dates fall out."""
    entries = []
    # 1. Sitemap (covers the most recent items)
    try:
        sitemap_xml = fetch_text(SITEMAP_URL)
        entries.extend(parse_sitemap(sitemap_xml))
    except Exception as e:
        print(f"Sitemap fetch/parse error: {e}", file=sys.stderr)

    # 2. RSS fallback – iterate pages until no new dates in range.
    for page in range(1, MAX_RSS_PAGES + 1):
        try:
            rss_xml = fetch_text(RSS_URL_TEMPLATE.format(page=page))
            page_entries = parse_rss(rss_xml)
            if not page_entries:
                # No entries in the wanted window → we can stop.
                break
            entries.extend(page_entries)
        except Exception as e:
            print(f"RSS page {page} error: {e}", file=sys.stderr)
            break
    # Deduplicate – keep first occurrence.
    seen = set()
    unique = []
    for u, d in entries:
        if u not in seen:
            seen.add(u)
            unique.append((u, d))
    return unique

def write_tsv(entries):
    os.makedirs(os.path.dirname(OUTPUT_TSV), exist_ok=True)
    with open(OUTPUT_TSV, 'w', encoding='utf-8') as f:
        for url, pub_date in sorted(set(entries)):
            f.write(f"{url}\t{pub_date.isoformat()}\n")

def print_counts(entries):
    cnt = Counter(d for _, d in entries)
    for day in sorted(cnt):
        print(f"{day}\t{cnt[day]}")

def main():
    entries = collect_entries()
    write_tsv(entries)
    print_counts(entries)

if __name__ == '__main__':
    main()
