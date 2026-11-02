#!/usr/bin/env python3
import sys, json, os, collections

# Ensure the project’s scraper directory is on the import path for polite_fetch.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from polite_fetch import fetch
except Exception as e:
    print('Failed to import polite_fetch:', e)
    sys.exit(1)

# Configuration
DOMAIN = 'yabiladi.com'
START = '20260925'
END = '20261025'
# Output TSV path (relative to repository root)
OUTPUT_TSV = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'yabiladi-com.tsv'))

def iso_date(yyyymmdd):
    return f"{yyyymmdd[:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:8]}"

def fetch_cdx():
    url = (
        f'https://web.archive.org/cdx/search/cdx?url={DOMAIN}/*'
        f'&from={START}&to={END}'
        f'&output=json&collapse=urlkey'
    )
    status, text, _ = fetch(url)
    if status != 200:
        print('Failed to fetch CDX, status', status)
        sys.exit(1)
    try:
        data = json.loads(text)
    except Exception as e:
        print('CDX JSON decode error:', e)
        sys.exit(1)
    header = data[0]
    rows = data[1:]
    idx_original = header.index('original')
    idx_timestamp = header.index('timestamp')
    entries = []
    for row in rows:
        original = row[idx_original]
        timestamp = row[idx_timestamp]
        # Simple heuristic: keep URLs that look like article slugs (contain a hyphen)
        if '-' not in original:
            continue
        date = iso_date(timestamp[:8])
        entries.append((original, date, timestamp))
    return entries

def write_tsv(entries):
    os.makedirs(os.path.dirname(OUTPUT_TSV), exist_ok=True)
    seen = set()
    uniq = []
    for url, date, _ in entries:
        if url not in seen:
            seen.add(url)
            uniq.append((url, date))
    uniq.sort(key=lambda x: (x[1], x[0]))
    with open(OUTPUT_TSV, 'w', encoding='utf-8') as f:
        for url, date in uniq:
            f.write(f"{url}\t{date}\n")
    return uniq

def main():
    raw_entries = fetch_cdx()
    if not raw_entries:
        print('No entries found in CDX range')
        sys.exit(1)
    target_days = {'2026-09-30', '2026-10-10', '2026-10-20'}
    day_counts = {d: 0 for d in target_days}
    kept = []
    for url, date, ts in raw_entries:
        # Stop early if we have enough for each target day and a reasonable total.
        if all(c >= 15 for c in day_counts.values()) and len(kept) >= 200:
            break
        status, page, _ = fetch(url)
        if status != 200 or not page or len(page) < 1500:
            continue
        kept.append((url, date, ts))
        if date in day_counts:
            day_counts[date] += 1
    if not kept:
        print('No suitable articles found')
        sys.exit(1)
    uniq = write_tsv(kept)
    counter = collections.Counter(date for _, date in uniq)
    for day in sorted(counter):
        print(f"{day}: {counter[day]} URLs")
    print(f"Wrote {len(uniq)} unique URLs to {OUTPUT_TSV}")
    for d in sorted(target_days):
        print(f"Target {d}: {day_counts.get(d,0)} URLs collected")

if __name__ == '__main__':
    main()

