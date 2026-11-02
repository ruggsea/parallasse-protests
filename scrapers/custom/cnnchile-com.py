import sys
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

# Ensure polite_fetch is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from polite_fetch import fetch
except ImportError:
    print('polite_fetch module not found')
    sys.exit(1)

# Base URLs for month sitemaps
def month_sitemap_urls(start: datetime, end: datetime):
    urls = []
    cur = datetime(start.year, start.month, 1)
    while cur <= end:
        urls.append(f'https://www.cnnchile.com/_files/sitemaps/{cur.year:04d}/{cur.month:02d}.xml')
        # increment month
        if cur.month == 12:
            cur = datetime(cur.year + 1, 1, 1)
        else:
            cur = datetime(cur.year, cur.month + 1, 1)
    return urls

# Additional sitemaps that may contain recent items
ADDITIONAL_SITEMAPS = [
    'https://www.cnnchile.com/_files/sitemaps/sitemap_news.xml',
    'https://www.cnnchile.com/_files/sitemaps/sitemap_lasts.xml',
]

START_DATE = datetime(2026, 9, 25).date()
END_DATE = datetime(2026, 10, 25).date()

def fetch_sitemap(url):
    status, text, _ = fetch(url)
    if status != 200:
        print(f'Failed to fetch sitemap {url}: status {status}')
        sys.exit(1)
    return text

def parse_sitemap(xml_text):
    # Use iterparse for memory efficiency
    for event, elem in ET.iterparse(sys.stdin if xml_text is None else ET.ElementTree(ET.fromstring(xml_text)).getroot().iter()):
        pass

def extract_entries(xml_text):
    # Parse whole XML (size is moderate)
    root = ET.fromstring(xml_text)
    ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9',
          'news': 'http://www.google.com/schemas/sitemap-news/0.9'}
    for url_el in root.findall('ns:url', ns):
        loc = url_el.find('ns:loc', ns)
        if loc is None:
            continue
        url = loc.text.strip()
        # Try news publication date first
        pub_date_el = url_el.find('news:news/news:publication_date', ns)
        if pub_date_el is not None:
            pub_dt = datetime.fromisoformat(pub_date_el.text.strip())
        else:
            # Fallback to lastmod element
            lastmod_el = url_el.find('ns:lastmod', ns)
            if lastmod_el is None:
                continue
            pub_dt = datetime.fromisoformat(lastmod_el.text.strip())
        if START_DATE <= pub_dt.date() <= END_DATE:
            yield url, pub_dt.date().isoformat()

def main():
    # Gather entries from month sitemaps covering the range
    dt_start = datetime(2026, 9, 25)
    dt_end = datetime(2026, 10, 25)
    all_entries = []
    for sitemap_url in month_sitemap_urls(dt_start, dt_end) + ADDITIONAL_SITEMAPS:
        try:
            xml = fetch_sitemap(sitemap_url)
            all_entries.extend(list(extract_entries(xml)))
        except SystemExit:
            # Skip failing sitemap but continue
            continue
    # Deduplicate by URL (keep first encountered date)
    uniq = {}
    for url, date_str in all_entries:
        if url not in uniq:
            uniq[url] = date_str
    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'cnnchile-com.tsv'))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        for url, date_str in sorted(uniq.items()):
            f.write(f"{url}\t{date_str}\n")
    # Print per‑day counts
    counts = {}
    for date_str in uniq.values():
        counts[date_str] = counts.get(date_str, 0) + 1
    for day in sorted(counts):
        print(f"{day}: {counts[day]} URLs")

if __name__ == '__main__':
    main()
