import sys, re, os, json, datetime

# Add project lib path for polite_fetch
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from polite_fetch import fetch

BASE = 'https://www.rts.rs'
START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)
OUT_TSV = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'rts-rs.tsv'))

def iso_date(d):
    return d.isoformat()

def fetch_home():
    status, text, _ = fetch(BASE)
    if status != 200:
        print(f'Failed to fetch home page, status {status}', file=sys.stderr)
        return ''
    return text

def extract_urls(html):
    # Find markdown-like links or href attributes
    urls = set()
    # pattern for https://www.rts.rs/... up to .html
    for m in re.findall(r'(https?://www\.rts\.rs/[^\s"\'<>]*?\.html)', html):
        urls.add(m)
    return urls

def parse_date_from_article(text):
    # look for pattern like "недеља, 25.10.2026, 21:46 ->"
    m = re.search(r'\b(\d{2}\.\d{2}\.\d{4})\b', text)
    if not m:
        return None
    day, month, year = map(int, m.group(1).split('.'))
    return datetime.date(year, month, day)

def main():
    html = fetch_home()
    if not html:
        sys.exit(1)
    urls = extract_urls(html)
    print(f'Found {len(urls)} candidate URLs on home page')
    results = []
    for url in sorted(urls):
        status, txt, _ = fetch(url)
        if status != 200:
            continue
        pub_date = parse_date_from_article(txt)
        if not pub_date:
            continue
        if START <= pub_date <= END:
            results.append((url, iso_date(pub_date)))
    # dedupe
    unique = {}
    for u, d in results:
        unique[u] = d
    # write TSV
    os.makedirs(os.path.dirname(OUT_TSV), exist_ok=True)
    with open(OUT_TSV, 'w', encoding='utf-8') as f:
        for u, d in sorted(unique.items()):
            f.write(f'{u}\t{d}\n')
    # print per‑day counts
    from collections import Counter
    cnt = Counter(d for d in unique.values())
    for day in (START + datetime.timedelta(days=i) for i in range((END-START).days+1)):
        print(f'{day}: {cnt.get(day.isoformat(), 0)} URLs')

if __name__ == '__main__':
    main()
