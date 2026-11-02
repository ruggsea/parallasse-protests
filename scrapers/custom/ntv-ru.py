import sys, os, re, datetime, xml.etree.ElementTree as ET

# Ensure polite_fetch is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from polite_fetch import fetch
except ImportError:
    print('polite_fetch module not found', file=sys.stderr)
    sys.exit(1)

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

SITEMAP_URL = 'https://www.ntv.ru/exp/yandex/sitemap_last.jsp'

def parse_date(date_str):
    # Expected ISO format e.g. 2026-10-26T10:07:34+04:00
    try:
        dt = datetime.datetime.fromisoformat(date_str)
        return dt.date()
    except Exception:
        return None

def fetch_sitemap(url):
    status, text, _ = fetch(url)
    if status != 200:
        print(f'Failed to fetch sitemap {url}: status {status}', file=sys.stderr)
        return None
    return text

def main():
    xml_text = fetch_sitemap(SITEMAP_URL)
    if not xml_text:
        sys.exit(1)
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        print('XML parse error:', e, file=sys.stderr)
        sys.exit(1)
    ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    # Some sitemaps use default namespace without prefix
    urls = []
    for url_el in root.findall('.//{*}url'):
        loc = url_el.find('{*}loc')
        lastmod = url_el.find('{*}lastmod')
        if loc is None or lastmod is None:
            continue
        url = loc.text.strip()
        date = parse_date(lastmod.text.strip())
        if date and START <= date <= END:
            urls.append((url, date.isoformat()))
    # Deduplicate
    uniq = {}
    for u, d in urls:
        uniq[u] = d
    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'ntv-ru.tsv') )
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        for u, d in sorted(uniq.items()):
            f.write(f"{u}\t{d}\n")
    # Simple stats per day
    from collections import Counter
    counter = Counter(d for _, d in uniq.items())
    for day in sorted(counter):
        print(f"{day}: {counter[day]} URLs")

if __name__ == '__main__':
    main()
