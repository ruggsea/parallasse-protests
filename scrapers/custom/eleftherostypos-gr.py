#!/usr/bin/env python3
import sys, os, csv, collections
from datetime import date, datetime, timezone

# Make polite_fetch importable (relative to this file)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from polite_fetch import fetch
except ImportError:
    raise ImportError('polite_fetch module not found')

# Configuration
START_DATE = date(2026, 9, 25)
END_DATE   = date(2026, 10, 25)
# Output TSV path (project root relative)
OUTPUT_TSV = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'eleftherostypos-gr.tsv'))

# Base sitemap index that lists other sitemaps (including post‑sitemaps). We will also fetch the dedicated news sitemap for recent items.
BASE_INDEX = 'https://www.eleftherostypos.gr/sitemap.xml'
BASE_NEWS = 'https://www.eleftherostypos.gr/sitemap_news.xml'

NS = {
    'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9',
    'news': 'http://www.google.com/schemas/sitemap-news/0.9'
}

def fetch_sitemap(url):
    status, text, _ = fetch(url)
    if status != 200:
        raise RuntimeError(f'Failed to fetch {url}, status {status}')
    return text

def parse_sitemap(xml_text):
    """Parse a sitemap XML and return (url, pub_date) pairs.
    Supports both news:sitemap entries (publication_date) and regular sitemap entries (lastmod)."""
    import xml.etree.ElementTree as ET
    root = ET.fromstring(xml_text)
    entries = []
    for el in root.findall('sm:url', NS):
        loc_el = el.find('sm:loc', NS)
        if loc_el is None:
            continue
        link = loc_el.text.strip()
        pub_date = None
        # Prefer news:publication_date if present
        news_el = el.find('news:news', NS)
        if news_el is not None:
            date_el = news_el.find('news:publication_date', NS)
            if date_el is not None:
                try:
                    dt = datetime.fromisoformat(date_el.text.strip())
                    pub_date = dt.astimezone(timezone.utc).date() if dt.tzinfo else dt.date()
                except Exception:
                    pass
        if pub_date is None:
            # Fallback to <lastmod>
            lastmod_el = el.find('sm:lastmod', NS)
            if lastmod_el is not None:
                try:
                    dt = datetime.fromisoformat(lastmod_el.text.strip())
                    pub_date = dt.astimezone(timezone.utc).date() if dt.tzinfo else dt.date()
                except Exception:
                    pass
        if pub_date is not None:
            entries.append((link, pub_date))
    return entries

def collect_all_entries():
    """Gather entries from the news sitemap (recent) and all post‑sitemaps listed in the index."""
    entries = []
    # News sitemap gives the freshest articles with explicit publication_date
    news_xml = fetch_sitemap(BASE_NEWS)
    entries.extend(parse_sitemap(news_xml))
    # Index sitemap lists many post‑sitemap files covering the archive
    index_xml = fetch_sitemap(BASE_INDEX)
    import xml.etree.ElementTree as ET
    root = ET.fromstring(index_xml)
    for sm in root.findall('sm:sitemap', NS):
        loc = sm.find('sm:loc', NS)
        if loc is None:
            continue
        loc_url = loc.text.strip()
        # We only care about post‑sitemaps (they contain <url> entries with <lastmod>)
        if 'post-sitemap' in loc_url:
            try:
                sm_xml = fetch_sitemap(loc_url)
                entries.extend(parse_sitemap(sm_xml))
            except Exception as e:
                # Log but continue
                print(f'Failed to process {loc_url}: {e}', file=sys.stderr)
    return entries

def main():
    all_entries = collect_all_entries()
    # Filter by desired window and deduplicate (keep first seen date)
    seen = {}
    for url, pub_date in all_entries:
        if pub_date < START_DATE or pub_date > END_DATE:
            continue
        if url not in seen:
            seen[url] = pub_date
    # Write TSV
    os.makedirs(os.path.dirname(OUTPUT_TSV), exist_ok=True)
    with open(OUTPUT_TSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, delimiter='\t')
        for url, pub_date in sorted(seen.items(), key=lambda x: (x[1], x[0])):
            writer.writerow([url, pub_date.isoformat()])
    # Print per‑day counts for quick sanity check
    counter = collections.Counter(seen.values())
    for d in sorted(counter):
        print(f"{d}: {counter[d]} URLs")
    print(f"Total URLs: {len(seen)}")

if __name__ == '__main__':
    main()
