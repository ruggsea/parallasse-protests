import sys, os, re, csv, datetime, xml.etree.ElementTree as ET

# Ensure path for polite_fetch
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from polite_fetch import fetch
except ImportError:
    print('polite_fetch not found')
    sys.exit(1)

BASE_URL = 'https://www.open.online'
SITEMAP_INDEX = f'{BASE_URL}/sitemap_index.xml'
START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

def fetch_xml(url):
    status, text, _ = fetch(url)
    if status != 200:
        print(f'Failed {status} fetching {url}')
        return None
    return ET.fromstring(text.encode('utf-8'))

def parse_date_from_url(url):
    # URL pattern .../YYYY/MM/DD/slug
    m = re.search(r'/([0-9]{4})/([0-9]{2})/([0-9]{2})/', url)
    if m:
        try:
            return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    return None

def main():
    # Get sitemap index
    root = fetch_xml(SITEMAP_INDEX)
    if root is None:
        return
    ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    sitemap_urls = [elem.find('ns:loc', ns).text for elem in root.findall('ns:sitemap', ns)]
    # Include the explicit news sitemap if not listed
    if f'{BASE_URL}/wp-content/uploads/sitemaps/www-open-online-sitemap-news.xml' not in sitemap_urls:
        sitemap_urls.append(f'{BASE_URL}/wp-content/uploads/sitemaps/www-open-online-sitemap-news.xml')
    results = []
    for sm_url in sitemap_urls:
        sm_root = fetch_xml(sm_url)
        if sm_root is None:
            continue
        for url_el in sm_root.findall('ns:url', ns):
            loc = url_el.find('ns:loc', ns).text
            # Skip plain homepage URLs which lack a date in the path
            if re.fullmatch(r'https?://[^/]+/?', loc):
                continue
            # Try get lastmod, but prefer date from URL path
            date = parse_date_from_url(loc)
            if not date:
                # fallback to lastmod if present
                lm_el = url_el.find('ns:lastmod', ns)
                if lm_el is not None:
                    try:
                        date = datetime.datetime.fromisoformat(lm_el.text).date()
                    except Exception:
                        continue
            if date and START <= date <= END:
                results.append((loc, date.isoformat()))
    # Deduplicate
    unique = {}
    for url, d in results:
        unique[url] = d
    # Write TSV
    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'open-online.tsv'))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', newline='') as f:
        writer = csv.writer(f, delimiter='\t')
        for url, d in sorted(unique.items()):
            writer.writerow([url, d])
    # Print per‑day counts
    counts = {}
    for _, d in unique.items():
        counts[d] = counts.get(d, 0) + 1
    for day in sorted(counts):
        print(f'{day}\t{counts[day]}')

if __name__ == '__main__':
    main()
