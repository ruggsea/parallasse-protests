import sys, os, datetime, json, re, collections

# Add project scrapers directory to import path for polite_fetch
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from polite_fetch import fetch

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

CDX_TEMPLATE = (
    'https://web.archive.org/cdx/search/cdx?url=www.khan.co.kr/article/*'
    '&from=20260925&to=20261025&output=json&collapse=urlkey&limit=10000&offset={offset}'
)

def fetch_cdx(offset: int):
    url = CDX_TEMPLATE.format(offset=offset)
    status, txt, _ = fetch(url)
    return status, txt

def main():
    all_entries = set()  # (url, date)
    offset = 0
    while True:
        status, txt = fetch_cdx(offset)
        if status != 200:
            print(f'CDX fetch failed at offset {offset}, status {status}', file=sys.stderr)
            break
        try:
            data = json.loads(txt)
        except Exception as e:
            print(f'JSON parse error at offset {offset}: {e}', file=sys.stderr)
            break
        if len(data) <= 1:  # only header row
            break
        for row in data[1:]:
            original = row[2]
            m = re.search(r'/article/(\d{8})', original)
            if not m:
                continue
            ymd = m.group(1)
            try:
                d = datetime.datetime.strptime(ymd, '%Y%m%d').date()
            except ValueError:
                continue
            if START <= d <= END:
                all_entries.add((original, d))
        offset += 10000
        # safety stop to avoid endless loop
        if offset > 2000000:
            break

    # Write TSV
    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'khan-co-kr.tsv'))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        for url, d in sorted(all_entries, key=lambda x: (x[1], x[0])):
            f.write(f"{url}\t{d.isoformat()}\n")

    # Print per‑day counts
    cnt = collections.Counter(d for _, d in all_entries)
    for d in sorted(cnt):
        print(f"{d}: {cnt[d]} URLs")

if __name__ == '__main__':
    main()
