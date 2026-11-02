import os
import sys
import datetime
import xml.etree.ElementTree as ET

# Ensure polite_fetch is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from polite_fetch import fetch
except ImportError:
    raise ImportError('polite_fetch module not found; ensure it is in scrapers directory')

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

SITEMAP_INDEX_URL = 'https://www.irna.ir/sitemap/all/sitemap.xml'

def fetch_url(url):
    status, text, _ = fetch(url)
    if status != 200:
        raise RuntimeError(f'Failed to fetch {url}: HTTP {status}')
    return text

def parse_dates(text):
    # namespaces used in the sitemap
    ns = {
        'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9',
        'news': 'http://www.google.com/schemas/sitemap-news/0.9'
    }
    root = ET.fromstring(text)
    urls = []
    for url_el in root.findall('ns:url', ns):
        loc_el = url_el.find('ns:loc', ns)
        if loc_el is None:
            continue
        url = loc_el.text.strip()
        # Prefer news:publication_date, fallback to lastmod
        pub_el = url_el.find('news:news/news:publication_date', ns)
        if pub_el is not None and pub_el.text:
            datestr = pub_el.text.strip()
        else:
            lastmod_el = url_el.find('ns:lastmod', ns)
            datestr = lastmod_el.text.strip() if lastmod_el is not None else None
        if not datestr:
            continue
        # Parse ISO datetime, remove trailing Z if present
        datestr = datestr.rstrip('Z')
        try:
            dt = datetime.datetime.fromisoformat(datestr)
        except ValueError:
            # fallback split
            dt = datetime.datetime.strptime(datestr, '%Y-%m-%dT%H:%M:%S')
        date = dt.date()
        if START <= date <= END:
            urls.append((url, date.isoformat()))
    return urls

def main():
    # Fetch sitemap index which lists per‑day sitemaps
    index_xml = fetch_url(SITEMAP_INDEX_URL)
    ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    root = ET.fromstring(index_xml)
    sitemap_urls = [loc.text.strip() for loc in root.findall('.//ns:loc', ns)]
    all_entries = []
    for sm_url in sitemap_urls:
        try:
            sm_text = fetch_url(sm_url)
            all_entries.extend(parse_dates(sm_text))
        except Exception as e:
            print(f'Warning: could not process {sm_url}: {e}', file=sys.stderr)
    # Deduplicate while preserving first occurrence
    seen = set()
    unique = []
    for url, date in all_entries:
        if url not in seen:
            seen.add(url)
            unique.append((url, date))
    # Write output TSV
    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'irna-ir.tsv'))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    import urllib.parse
    with open(out_path, 'w', encoding='utf-8') as f:
        for url, date in unique:
            enc_url = urllib.parse.quote(url, safe=':/')
            f.write(f"{enc_url}\t{date}\n")
    # Print per‑day counts
    counts = {}
    for _, date in unique:
        counts[date] = counts.get(date, 0) + 1
    for d in sorted(counts):
        print(f"{d}\t{counts[d]}")
    print(f"Total URLs written: {len(unique)}")

if __name__ == '__main__':
    main()
