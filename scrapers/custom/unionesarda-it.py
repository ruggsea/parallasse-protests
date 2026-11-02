import sys, os, xml.etree.ElementTree as ET, datetime, json, time
from pathlib import Path

# Add scrapers dir to sys.path for polite_fetch import
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from polite_fetch import fetch
except ImportError:
    print('polite_fetch not found')
    sys.exit(1)

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)
OUT_TSV = Path(__file__).parents[2] / 'data' / 'urls_custom' / 'unionesarda-it.tsv'
OUT_TSV.parent.mkdir(parents=True, exist_ok=True)

def parse_sitemap(url):
    status, text, _ = fetch(url)
    if status != 200:
        print(f'Failed to fetch sitemap {url}: {status}')
        return []
    root = ET.fromstring(text)
    ns = {'news': 'http://www.google.com/schemas/sitemap-news/0.9'}
    entries = []
    for url_el in root.findall('{http://www.sitemaps.org/schemas/sitemap/0.9}url'):
        pub_el = url_el.find('news:news/news:publication_date', ns)
        if pub_el is not None and pub_el.text:
            date_str = pub_el.text[:10]
        else:
            lm_el = url_el.find('{http://www.sitemaps.org/schemas/sitemap/0.9}lastmod')
            if lm_el is None or not lm_el.text:
                continue
            date_str = lm_el.text[:10]
        try:
            d = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            continue
        if START <= d <= END:
            loc = url_el.find('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
            if loc is not None and loc.text:
                entries.append((loc.text.strip(), d.isoformat()))
    return entries

def fetch_wayback(day):
    # day is datetime.date, fetch URLs from that day via CDX
    from_day = day.isoformat().replace('-', '')
    to_day = from_day
    cdx_url = (
        f'https://web.archive.org/cdx/search/cdx?url=www.unionesarda.it/*'
        f'&from={from_day}&to={to_day}&output=json&fl=original,timestamp&collapse=urlkey&limit=5000'
    )
    status, text, _ = fetch(cdx_url)
    if status != 200:
        print(f'Wayback CDX fetch failed for {day}: {status}')
        return []
    try:
        data = json.loads(text)
    except Exception:
        return []
    # first row is header
    entries = []
    for row in data[1:]:
        url, ts = row
        entries.append((url, day.isoformat()))
    return entries

def main():
    all_entries = {}
    # 1. Try news sitemap
    sitemap_url = 'https://www.unionesarda.it/sitemaps/sitemap_news1.xml'
    entries = parse_sitemap(sitemap_url)
    for url, d in entries:
        all_entries.setdefault(d, set()).add(url)
    # Check per‑day counts, augment with Wayback if needed
    needed_days = [START + datetime.timedelta(days=i) for i in range((END-START).days + 1)]
    for day in needed_days:
        d_str = day.isoformat()
        cnt = len(all_entries.get(d_str, []))
        if cnt < 15:
            # fetch from Wayback
            wb_entries = fetch_wayback(day)
            for url, _ in wb_entries:
                all_entries.setdefault(d_str, set()).add(url)
    # Write TSV
    total_written = 0
    with OUT_TSV.open('w', encoding='utf-8') as f:
        for d in sorted(all_entries.keys()):
            for url in sorted(all_entries[d]):
                f.write(f"{url}\t{d}\n")
                total_written += 1
    # Print per‑day counts
    print('Written', total_written, 'URLs')
    for day in needed_days:
        d_str = day.isoformat()
        cnt = len(all_entries.get(d_str, []))
        if cnt:
            print(d_str, cnt)

if __name__ == '__main__':
    main()
