#!/usr/bin/env python3
import sys, os, datetime, time, json, collections
import email.utils

# polite_fetch must be on sys.path (parent of scrapers)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from polite_fetch import fetch

BASE_DOMAIN = 'alsharqiya.com'
START_DATE = datetime.date(2026, 9, 25)
END_DATE   = datetime.date(2026, 10, 25)
OUTPUT_TSV = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'alsharqiya-com.tsv'))

CDX_URL = (
    'https://web.archive.org/cdx/search/cdx'
    '?url={domain}/*'
    '&from={from_date}&to={to_date}'
    '&output=json'
    '&collapse=urlkey'
)

def fetch_cdx(domain, from_date, to_date, retries=5, backoff=5):
    url = CDX_URL.format(domain=domain, from_date=from_date, to_date=to_date)
    for attempt in range(1, retries+1):
        status, text, _ = fetch(url)
        if status == 200:
            return text
        print(f'CDX fetch attempt {attempt} failed with status {status}, retrying after {backoff}s')
        time.sleep(backoff * attempt)
    print('All CDX attempts failed')
    return ''

def parse_cdx(json_text):
    try:
        data = json.loads(json_text)
    except Exception as e:
        print('Failed to parse CDX JSON:', e)
        return {}
    # First entry is header list, e.g. ["urlkey","timestamp",...]
    if not data or not isinstance(data, list) or not isinstance(data[0], list):
        return {}
    header = data[0]
    url_idx = header.index('url') if 'url' in header else 0
    timestamp_idx = header.index('timestamp') if 'timestamp' in header else 1
    collected = {}
    for row in data[1:]:
        url = row[url_idx]
        ts = row[timestamp_idx]
        # timestamp format YYYYMMDDhhmmss
        try:
            dt = datetime.datetime.strptime(ts, '%Y%m%d%H%M%S')
        except Exception:
            continue
        date = dt.date()
        if START_DATE <= date <= END_DATE:
            collected[url] = date
    return collected

def main():
    # Try RSS first (may be empty)
    # Skipping RSS because it was empty for this site.
    # Use Wayback CDX as primary source
    cdx_text = fetch_cdx(BASE_DOMAIN, START_DATE.isoformat().replace('-',''), END_DATE.isoformat().replace('-',''))
    if not cdx_text:
        print('No CDX data retrieved')
        return
    collected = parse_cdx(cdx_text)
    if not collected:
        print('No URLs parsed from CDX')
        return
    os.makedirs(os.path.dirname(OUTPUT_TSV), exist_ok=True)
    with open(OUTPUT_TSV, 'w', encoding='utf-8') as f:
        for url, date in sorted(collected.items()):
            f.write(f"{url}\t{date.isoformat()}\n")
    # Print per‑day counts
    counts = collections.Counter(d.isoformat() for d in collected.values())
    for day in sorted(counts):
        print(f"{day}: {counts[day]}")

if __name__ == '__main__':
    main()
