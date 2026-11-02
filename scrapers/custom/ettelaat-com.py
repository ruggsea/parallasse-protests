#!/usr/bin/env python3
import sys, os, datetime, xml.etree.ElementTree as ET

# Insert path for polite_fetch
scraper_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, scraper_dir)
try:
    from polite_fetch import fetch
except ImportError:
    print('polite_fetch not found', file=sys.stderr)
    sys.exit(1)

def parse_date(date_str):
    # Expected ISO format like 2026-10-25T22:06:04Z
    try:
        return datetime.datetime.fromisoformat(date_str.replace('Z', '+00:00')).date()
    except Exception:
        # fallback simple split
        return datetime.date.fromisoformat(date_str.split('T')[0])

def main():
    start = datetime.date(2026, 9, 25)
    end = datetime.date(2026, 10, 25)
    # First fetch the sitemap index that lists per‑day sitemaps.
    index_url = 'https://www.ettelaat.com/sitemap/all/sitemap.xml'
    status, index_text, _ = fetch(index_url)
    if status != 200:
        print(f'Failed to fetch sitemap index {index_url}: status {status}', file=sys.stderr)
        sys.exit(1)
    index_root = ET.fromstring(index_text)
    ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    sitemap_urls = [loc.text.strip() for loc in index_root.findall('.//ns:loc', ns)]
    entries = []
    # Namespace for news in each sitemap
    ns_news = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9',
               'news': 'http://www.google.com/schemas/sitemap-news/0.9'}
    for sm_url in sitemap_urls:
        status, sm_text, _ = fetch(sm_url)
        if status != 200:
            # skip missing or blocked sitemaps
            continue
        try:
            sm_root = ET.fromstring(sm_text)
        except ET.ParseError:
            continue
        for url_el in sm_root.findall('ns:url', ns_news):
            loc_el = url_el.find('ns:loc', ns_news)
            # Try news:publication_date first, fall back to lastmod
            pub_el = url_el.find('news:news/news:publication_date', ns_news)
            if pub_el is None:
                pub_el = url_el.find('ns:lastmod', ns_news)
            if loc_el is None or pub_el is None:
                continue
            raw_url = loc_el.text.strip()
            # Encode Unicode characters in URL for reliable fetching
            from urllib.parse import quote
            url = quote(raw_url, safe=':/')
            pub_date = parse_date(pub_el.text.strip())
            if start <= pub_date <= end:
                entries.append((url, pub_date.isoformat()))
    # Deduplicate while preserving order
    seen = set()
    uniq = []
    for url, d in entries:
        if url not in seen:
            seen.add(url)
            uniq.append((url, d))
    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../data/urls_custom/ettelaat-com.tsv'))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        for url, d in uniq:
            f.write(f"{url}\t{d}\n")
    # Print per‑day counts
    from collections import Counter
    cnt = Counter(d for _, d in uniq)
    for day in sorted(cnt.keys()):
        print(f"{day}: {cnt[day]} URLs")
    print(f"Total URLs written: {len(uniq)}")

if __name__ == '__main__':
    main()
