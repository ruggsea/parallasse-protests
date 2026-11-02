import sys
import os
import datetime
import xml.etree.ElementTree as ET
from collections import defaultdict

# Ensure polite_fetch is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from polite_fetch import fetch
except ImportError:
    print('polite_fetch not found')
    sys.exit(1)

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

def iso_date(dt_str):
    """Parse various ISO datetime strings and return date object."""
    try:
        # datetime.fromisoformat handles offset
        return datetime.datetime.fromisoformat(dt_str).date()
    except Exception:
        # fallback: split at T
        try:
            return datetime.datetime.strptime(dt_str.split('T')[0], '%Y-%m-%d').date()
        except Exception:
            return None

def fetch_xml(url):
    status, text, _ = fetch(url)
    if status != 200:
        print(f'Failed to fetch {url}: {status}')
        return None
    return text

def parse_sitemap(text):
    """Parse a sitemap XML text, return dict url->date"""
    ns = {
        'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9',
        'news': 'http://www.google.com/schemas/sitemap-news/0.9'
    }
    root = ET.fromstring(text)
    results = {}
    for url_el in root.findall('sm:url', ns):
        loc_el = url_el.find('sm:loc', ns)
        if loc_el is None:
            continue
        url = loc_el.text.strip()
        # Try news:publication_date first
        pub_el = url_el.find('.//news:publication_date', ns)
        if pub_el is not None and pub_el.text:
            date = iso_date(pub_el.text.strip())
        else:
            # fallback to lastmod
            mod_el = url_el.find('sm:lastmod', ns)
            if mod_el is not None and mod_el.text:
                date = iso_date(mod_el.text.strip())
            else:
                date = None
        if date:
            results[url] = date
    return results

def collect():
    all_urls = {}
    # Primary news sitemap
    news_sitemap = 'https://www.bild.de/sitemap-news.xml'
    txt = fetch_xml(news_sitemap)
    if txt:
        all_urls.update(parse_sitemap(txt))
    # Monthly sitemaps via sitemap-index.xml
    index_url = 'https://www.bild.de/sitemap-index.xml'
    txt = fetch_xml(index_url)
    if txt:
        # parse index to get month files
        ns = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        root = ET.fromstring(txt)
        for sm_el in root.findall('sm:sitemap', ns):
            loc = sm_el.find('sm:loc', ns)
            if loc is None:
                continue
            url = loc.text.strip()
            # Only interest in 2026-09 and 2026-10 files
            if any(month in url for month in ('202610', '202609')):
                sm_txt = fetch_xml(url)
                if sm_txt:
                    all_urls.update(parse_sitemap(sm_txt))
    # Filter by date range
    filtered = {u: d for u, d in all_urls.items() if START <= d <= END}
    return filtered

def write_tsv(data):
    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'bild-de.tsv') )
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    # sort by date then url
    with open(out_path, 'w', encoding='utf-8') as f:
        for url, dt in sorted(data.items(), key=lambda x: (x[1], x[0])):
            f.write(f"{url}\t{dt.isoformat()}\n")
    return out_path

def main():
    data = collect()
    out_file = write_tsv(data)
    # per-day counts
    counts = defaultdict(int)
    for d in data.values():
        counts[d.isoformat()] += 1
    for day in sorted(counts):
        print(f"{day}: {counts[day]} URLs")
    print(f"Wrote {len(data)} total URLs to {out_file}")

if __name__ == '__main__':
    main()
