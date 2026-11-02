import os
import sys
import datetime
import xml.etree.ElementTree as ET

# Add project scrapers directory to path for polite_fetch import
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from polite_fetch import fetch
except ImportError as e:
    raise RuntimeError('polite_fetch module not found')

def iso_date(s: str) -> datetime.date:
    """Extract YYYY-MM-DD from ISO datetime string"""
    return datetime.datetime.fromisoformat(s.rstrip('Z')).date()

def fetch_xml(url: str) -> ET.Element:
    # polite_fetch returns a tuple (status, body, info). Use body for XML.
    result = fetch(url)
    if not isinstance(result, tuple) or len(result) < 2:
        raise RuntimeError(f'Unexpected fetch result for {url}: {result}')
    txt = result[1]
    return ET.fromstring(txt)

def main():
    # Date window
    start = datetime.date(2026, 9, 25)
    end = datetime.date(2026, 10, 25)
    # Target dates that need at least 15 URLs each
    targets = {
        datetime.date(2026, 9, 30): [],
        datetime.date(2026, 10, 10): [],
        datetime.date(2026, 10, 20): [],
    }
    all_urls = set()
    url_to_date = {}
    # Sitemap index
    sitemap_index_url = 'https://www.idl-reporteros.pe/wp-sitemap.xml'
    index_root = fetch_xml(sitemap_index_url)
    sitemap_urls = [loc.text for loc in index_root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}loc')]
    for sm_url in sitemap_urls:
        # Only post sitemaps (skip others)
        if 'wp-sitemap-posts' not in sm_url:
            continue
        try:
            sm_root = fetch_xml(sm_url)
        except Exception as exc:
            # Skip failing sitemap but continue
            print(f'Failed to fetch {sm_url}: {exc}', file=sys.stderr)
            continue
        for url_el in sm_root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}url'):
            loc_el = url_el.find('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
            lastmod_el = url_el.find('{http://www.sitemaps.org/schemas/sitemap/0.9}lastmod')
            if loc_el is None or lastmod_el is None:
                continue
            url = loc_el.text.strip()
            try:
                mod_date = iso_date(lastmod_el.text.strip())
            except Exception:
                continue
            if start <= mod_date <= end:
                if url in all_urls:
                    continue
                all_urls.add(url)
                url_to_date[url] = mod_date.isoformat()
                if mod_date in targets:
                    targets[mod_date].append(url)
    # Verify target counts
    for d, lst in targets.items():
        if len(lst) < 15:
            print(f'Warning: only {len(lst)} URLs for {d}', file=sys.stderr)
    # Write TSV (URL<TAB>YYYY-MM-DD)
    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'idl-reporteros-pe.tsv'))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        for url in sorted(all_urls):
            f.write(f"{url}\t{url_to_date.get(url, '')}\n")
    # Summary print
    total = len(all_urls)
    print(f'Collected {total} URLs between {start} and {end}.')
    for d, lst in targets.items():
        print(f'{d}: {len(lst)} URLs')

if __name__ == '__main__':
    main()
