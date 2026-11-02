#!/usr/bin/env python3
import sys, os, re, xml.etree.ElementTree as ET, datetime

# Ensure imports path for polite_fetch
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from polite_fetch import fetch

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

SITEMAP_INDEX = 'https://www.faz.net/sitemap-index.xml'

def fetch_sitemap(url):
    status, text, _ = fetch(url)
    if status != 200:
        raise RuntimeError(f'Failed to fetch sitemap {url}, status {status}')
    return text
    status, text, _ = fetch(url)
    if status != 200:
        raise RuntimeError(f'Failed to fetch sitemap {url}, status {status}')
    return text

def parse_sitemap(xml_text):
    # Namespace handling
    ns = {
        'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9',
        'news': 'http://www.google.com/schemas/sitemap-news/0.9'
    }
    root = ET.fromstring(xml_text)
    for url_el in root.findall('ns:url', ns):
        loc = url_el.find('ns:loc', ns)
        # Try news publication date first
        pub = url_el.find('news:news/news:publication_date', ns)
        if loc is None:
            continue
        url = loc.text.strip()
        date_str = None
        if pub is not None and pub.text:
            date_str = pub.text[:10]
        else:
            # Fallback to <lastmod>
            lastmod = url_el.find('ns:lastmod', ns)
            if lastmod is not None and lastmod.text:
                date_str = lastmod.text[:10]
        if not date_str:
            continue
        try:
            pub_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            continue
        if START <= pub_date <= END:
            yield url, pub_date

def main():
    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'faz-net.tsv'))
    urls_by_date = {}

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    # Fetch sitemap index and collect all sitemap URLs
    index_xml = fetch_sitemap(SITEMAP_INDEX)
    # Extract <loc> entries
    ns_idx = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    try:
        root_idx = ET.fromstring(index_xml)
    except ET.ParseError as e:
        raise RuntimeError(f'Failed to parse sitemap index: {e}')
    sitemap_urls = []
    for sm in root_idx.findall('ns:sitemap/ns:loc', ns_idx):
        if sm.text:
            sitemap_urls.append(sm.text.strip())
    # Also include the news-specific sitemap which may not be listed
    sitemap_urls.append('https://www.faz.net/sitemap-news.xml')
    # Parse each fetched sitemap
    for sm_url in sitemap_urls:
        try:
            xml_text = fetch_sitemap(sm_url)
        except Exception as e:
            print(f'Warning: could not fetch {sm_url}: {e}', file=sys.stderr)
            continue
        for url, pub_date in parse_sitemap(xml_text):
            urls_by_date.setdefault(pub_date, set()).add(url)

    # Write TSV sorted by date then url
    total = 0
    with open(out_path, 'w', encoding='utf-8') as f:
        for day in sorted(urls_by_date):
            for u in sorted(urls_by_date[day]):
                f.write(f"{u}\t{day.isoformat()}\n")
                total += 1
    # Print per‑day counts
    for day in sorted(urls_by_date):
        print(f"{day}: {len(urls_by_date[day])} URLs")
    print(f"Total URLs written: {total}")

if __name__ == '__main__':
    main()
