import sys, os, datetime, xml.etree.ElementTree as ET, csv

# Ensure import path for polite_fetch
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from polite_fetch import fetch
except ImportError:
    print('polite_fetch not found', file=sys.stderr)
    sys.exit(1)

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

SITEMAP_URLS = [
    'https://www.eleconomista.com.mx/sitemap-daily.xml',
    'https://www.eleconomista.com.mx/sitemap-google-news.xml',
]

def iso_to_date(s):
    # s like 2026-10-25T23:50:04-06:00
    try:
        dt = datetime.datetime.fromisoformat(s.replace('Z','+00:00'))
    except Exception:
        # fallback split
        dt = datetime.datetime.strptime(s[:19], '%Y-%m-%dT%H:%M:%S')
    return dt.date()

def fetch_sitemap(url):
    status, text, _ = fetch(url)
    if status != 200:
        print(f'Failed to fetch {url}: {status}', file=sys.stderr)
        sys.exit(1)
    return text

def parse_sitemap(xml_text):
    ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9',
          'news': 'http://www.google.com/schemas/sitemap-news/0.9'}
    root = ET.fromstring(xml_text)
    for url_el in root.findall('ns:url', ns):
        loc_el = url_el.find('ns:loc', ns)
        if loc_el is None:
            continue
        url = loc_el.text.strip()
        # Try news:publication_date first
        pubdate_el = url_el.find('.//news:publication_date', ns)
        if pubdate_el is not None:
            pubdate = iso_to_date(pubdate_el.text.strip())
        else:
            # fallback to <lastmod>
            lastmod_el = url_el.find('ns:lastmod', ns)
            if lastmod_el is None:
                continue
            pubdate = iso_to_date(lastmod_el.text.strip())
        if START <= pubdate <= END:
            yield url, pubdate

def main():
    entries = []
    for sitemap_url in SITEMAP_URLS:
        xml = fetch_sitemap(sitemap_url)
        entries.extend(list(parse_sitemap(xml)))
    # deduplicate while preserving first occurrence
    seen = set()
    uniq = []
    for url, dt in entries:
        if url in seen:
            continue
        seen.add(url)
        uniq.append((url, dt))
    # sort by date then url
    uniq.sort(key=lambda x: (x[1], x[0]))
    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'eleconomista-com-mx.tsv'))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, delimiter='\t')
        for url, dt in uniq:
            writer.writerow([url, dt.isoformat()])
    # simple stats per day for three check dates
    day_counts = {datetime.date(2026,9,30):0,
                  datetime.date(2026,10,10):0,
                  datetime.date(2026,10,20):0}
    for _, dt in uniq:
        if dt in day_counts:
            day_counts[dt] += 1
    print('Wrote', len(uniq), 'URLs to', out_path)
    for d, cnt in day_counts.items():
        print(f'{d.isoformat()}: {cnt} URLs')

if __name__ == '__main__':
    main()
