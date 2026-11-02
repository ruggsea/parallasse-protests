import sys, os, csv, datetime, xml.etree.ElementTree as ET

# Ensure path for polite_fetch
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from polite_fetch import fetch
except ImportError:
    print('polite_fetch not found', file=sys.stderr)
    sys.exit(1)

BASE_URL = 'https://elmercurio.com.ec'
SITEMAP_INDEX = f'{BASE_URL}/sitemap_index.xml'
OUT_TSV = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../data/urls_custom/elmercurio-com-ec.tsv'))

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

def fetch_xml(url):
    status, text, _ = fetch(url)
    if status != 200:
        print(f'Failed {status} fetching {url}', file=sys.stderr)
        return None
    return ET.fromstring(text)

def parse_sitemap(sitemap_url):
    root = fetch_xml(sitemap_url)
    if root is None:
        return []
    ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    entries = []
    for url_el in root.findall('ns:url', ns):
        loc = url_el.find('ns:loc', ns)
        lastmod = url_el.find('ns:lastmod', ns)
        if loc is None:
            continue
        url = loc.text.strip()
        date_str = lastmod.text.strip() if lastmod is not None else None
        date = None
        if date_str:
            try:
                # handle timezone offset
                date = datetime.datetime.fromisoformat(date_str.replace('Z', '+00:00')).date()
            except Exception:
                try:
                    date = datetime.datetime.strptime(date_str[:10], '%Y-%m-%d').date()
                except Exception:
                    date = None
        entries.append((url, date))
    return entries

def main():
    # fetch index
    idx_root = fetch_xml(SITEMAP_INDEX)
    if idx_root is None:
        sys.exit(1)
    ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    sitemap_urls = [el.find('ns:loc', ns).text.strip() for el in idx_root.findall('ns:sitemap', ns) if el.find('ns:loc', ns) is not None]
    all_entries = []
    for sm_url in sitemap_urls:
        all_entries.extend(parse_sitemap(sm_url))
    # filter by date range
    filtered = []
    for url, date in all_entries:
        if date is None:
            continue
        if START <= date <= END:
            filtered.append((url, date.isoformat()))
    # deduplicate preserving first date encountered
    seen = set()
    unique = []
    for url, d in filtered:
        if url not in seen:
            seen.add(url)
            unique.append((url, d))
    # sort by date then url
    unique.sort(key=lambda x: (x[1], x[0]))
    os.makedirs(os.path.dirname(OUT_TSV), exist_ok=True)
    with open(OUT_TSV, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f, delimiter='\t')
        for url, d in unique:
            w.writerow([url, d])
    # print per‑day counts
    from collections import Counter
    cnt = Counter([d for _, d in unique])
    for day in sorted(cnt.keys()):
        print(f'{day}\t{cnt[day]}')

if __name__ == '__main__':
    main()
