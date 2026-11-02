import sys, os, re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

# Ensure polite_fetch is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from polite_fetch import fetch
except ImportError:
    raise ImportError('polite_fetch module not found; ensure it exists in scrapers/')

OUT_TSV = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'offnews-bg.tsv'))
START = datetime(2026, 9, 25)
END = datetime(2026, 10, 25)

def fetch_url(url):
    status, text, _ = fetch(url)
    return status, text

def parse_sitemap(xml_text):
    """Parse a sitemap XML and yield (url, lastmod) tuples."""
    root = ET.fromstring(xml_text)
    ns = {'ns': root.tag.split('}')[0].strip('{')} if '}' in root.tag else {}
    for url_el in root.findall('ns:url', ns) if ns else root.findall('url'):
        loc = url_el.find('ns:loc', ns).text if ns else url_el.find('loc').text
        lastmod_el = url_el.find('ns:lastmod', ns) if ns else url_el.find('lastmod')
        lastmod = lastmod_el.text if lastmod_el is not None else None
        yield loc.strip(), (lastmod.strip() if lastmod else None)

def is_in_range(date_str):
    try:
        d = datetime.strptime(date_str[:10], '%Y-%m-%d')
        return START <= d <= END
    except Exception:
        return False

def write_tsv(pairs):
    os.makedirs(os.path.dirname(OUT_TSV), exist_ok=True)
    with open(OUT_TSV, 'w', encoding='utf-8') as f:
        for url, date in pairs:
            f.write(f"{url}\t{date}\n")

def main():
    # 1. Try sitemap index
    sitemap_index_url = 'https://offnews.bg/sitemap/index.xml'
    status, text = fetch_url(sitemap_index_url)
    urls_dates = []
    if status == 200:
        # Parse sitemap index for individual sitemaps
        root = ET.fromstring(text)
        ns = {'ns': root.tag.split('}')[0].strip('{')} if '}' in root.tag else {}
        sitemap_urls = []
        for sm in root.findall('ns:sitemap', ns) if ns else root.findall('sitemap'):
            loc_el = sm.find('ns:loc', ns) if ns else sm.find('loc')
            if loc_el is not None:
                sitemap_urls.append(loc_el.text.strip())
        # Visit each sitemap, collect URLs within range
        for sm_url in sitemap_urls:
            s_status, s_text = fetch_url(sm_url)
            if s_status != 200:
                continue
            for url, lastmod in parse_sitemap(s_text):
                if lastmod and is_in_range(lastmod):
                    urls_dates.append((url, lastmod[:10]))
    # 2. If not enough URLs, fallback to Wayback CDX
    if len(urls_dates) < 50:
        cdx_url = (
            'https://webcache.googleusercontent.com/search?q=cache:'  # placeholder, will be replaced
        )
        # Use Wayback CDX API directly
        cdx_api = (
            f'https://web.archive.org/cdx/search/cdx?url=offnews.bg/*'
            f'&from=20260925&to=20261025&output=json&fl=original,timestamp&collapse=urlkey'
        )
        c_status, c_text = fetch_url(cdx_api)
        if c_status == 200:
            import json
            rows = json.loads(c_text)
            # First row is header
            for row in rows[1:]:
                original, ts = row
                # Convert timestamp YYYYMMDDhhmmss to date
                date_part = ts[:8]
                try:
                    d = datetime.strptime(date_part, '%Y%m%d')
                except Exception:
                    continue
                if START <= d <= END:
                    date_str = d.strftime('%Y-%m-%d')
                    urls_dates.append((original, date_str))
    # Deduplicate
    uniq = {}
    for u, d in urls_dates:
        uniq[u] = d
    # Sort by date then url
    sorted_items = sorted(uniq.items(), key=lambda x: (x[1], x[0]))
    write_tsv(sorted_items)
    # Print per‑day counts
    from collections import Counter
    cnt = Counter(d for _, d in sorted_items)
    for day in sorted(cnt):
        print(f"{day}\t{cnt[day]}")

if __name__ == '__main__':
    main()
