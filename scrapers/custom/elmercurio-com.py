#!/usr/bin/env python3
import sys, os, json, csv, datetime, collections

# Ensure polite_fetch is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from polite_fetch import fetch
except ImportError:
    print('polite_fetch module not found', file=sys.stderr)
    sys.exit(1)

DOMAIN = 'elmercurio.com'
START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)
OUT_TSV = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'elmercurio-com.tsv'))

def fetch_day(day: datetime.date):
    base = 'https://web.archive.org/cdx/search/cdx'
    date_str = day.strftime('%Y%m%d')
    params = f'url={DOMAIN}/*&from={date_str}&to={date_str}&output=json&collapse=urlkey'
    url = f'{base}?{params}'
    status, text, _ = fetch(url)
    if status != 200:
        print(f'CDX fetch failed for {day} status {status}', file=sys.stderr)
        return []
    data = json.loads(text)
    if not data:
        return []
    header = data[0]
    url_idx = header.index('url') if 'url' in header else 0
    ts_idx = header.index('timestamp') if 'timestamp' in header else 1
    results = []
    for row in data[1:]:
        u = row[url_idx]
        ts = row[ts_idx]
        results.append((u, ts))
    return results

def extract_date(ts):
    try:
        return datetime.datetime.strptime(ts[:8], '%Y%m%d').date()
    except Exception:
        return None

def is_article(url: str) -> bool:
    # simple heuristic: contains '/noticias/' and ends with .aspx
    return '/noticias/' in url.lower() and url.lower().endswith('.aspx')

def main():
    per_day = collections.defaultdict(set)
    all_urls = set()
    cur = START
    while cur <= END:
        for url, ts in fetch_day(cur):
            if not is_article(url):
                continue
            dt = extract_date(ts)
            if dt is None:
                continue
            if url in all_urls:
                continue
            all_urls.add(url)
            per_day[dt].add(url)
        cur += datetime.timedelta(days=1)
    os.makedirs(os.path.dirname(OUT_TSV), exist_ok=True)
    with open(OUT_TSV, 'w', newline='') as f:
        writer = csv.writer(f, delimiter='\t')
        for day in sorted(per_day):
            for url in sorted(per_day[day]):
                writer.writerow([url, day.isoformat()])
    for day in sorted(per_day):
        print(f'{day}: {len(per_day[day])} URLs')

if __name__ == '__main__':
    main()
