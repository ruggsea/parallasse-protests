#!/usr/bin/env python3
import sys, os, datetime, xml.etree.ElementTree as ET

# Ensure polite_fetch is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from polite_fetch import fetch
except ImportError:
    print('polite_fetch module not found', file=sys.stderr)
    sys.exit(1)

START_DATE = datetime.date(2026, 9, 25)
END_DATE = datetime.date(2026, 10, 25)
SITEMAP_URL = 'https://news.ltn.com.tw/sitemap.xml'
OUTPUT_TSV = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../data/urls_custom/ltn-com-tw.tsv'))

def fetch_sitemap(url):
    status, text, _ = fetch(url)
    if status != 200:
        print(f'Failed to fetch sitemap: HTTP {status}', file=sys.stderr)
        sys.exit(1)
    return text

def parse_sitemap(xml_text):
    # Namespace handling
    ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9', 'news': 'http://www.google.com/schemas/sitemap-news/0.9'}
    root = ET.fromstring(xml_text)
    for url_elem in root.findall('ns:url', ns):
        loc = url_elem.find('ns:loc', ns)
        pub = url_elem.find('news:news/news:publication_date', ns)
        if loc is None or pub is None:
            continue
        url = loc.text.strip()
        pub_dt = pub.text.strip()
        # extract date part
        try:
            pub_date = datetime.datetime.fromisoformat(pub_dt).date()
        except Exception:
            # fallback: split at T
            pub_date = datetime.datetime.strptime(pub_dt.split('T')[0], '%Y-%m-%d').date()
        yield url, pub_date

def main():
    xml = fetch_sitemap(SITEMAP_URL)
    entries = []
    for url, pub_date in parse_sitemap(xml):
        if START_DATE <= pub_date <= END_DATE:
            entries.append((url, pub_date))
    # deduplicate by url, keep earliest date if duplicates (should be same)
    uniq = {}
    for url, pub_date in entries:
        if url not in uniq:
            uniq[url] = pub_date
    # sort by date then url
    sorted_items = sorted(uniq.items(), key=lambda x: (x[1], x[0]))
    os.makedirs(os.path.dirname(OUTPUT_TSV), exist_ok=True)
    with open(OUTPUT_TSV, 'w', encoding='utf-8') as f:
        for url, pub_date in sorted_items:
            f.write(f"{url}\t{pub_date.isoformat()}\n")
    # report counts per day
    from collections import Counter
    counter = Counter([d.isoformat() for _, d in sorted_items])
    for day in sorted(counter):
        print(f"{day}: {counter[day]} URLs")
    print(f"Total URLs written: {len(sorted_items)}")

if __name__ == '__main__':
    main()
