#!/usr/bin/env python3
import sys, json, datetime, os
from urllib.parse import urlparse

# Add scraper path for polite_fetch
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from polite_fetch import fetch
except ImportError:
    print('polite_fetch not found', file=sys.stderr)
    sys.exit(1)

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)
CDX_URL = (
    'https://web.archive.org/cdx/search/cdx?url=tn.com.ar/*'
    f'&from={START.isoformat().replace("-", "")}'
    f'&to={END.isoformat().replace("-", "")}'
    '&output=json&collapse=urlkey&fl=original,timestamp'
)

import time, re
from urllib.parse import urljoin

def fetch_cdx():
    for attempt in range(3):
        status, text, _ = fetch(CDX_URL)
        if status == 200:
            return text
        print(f'Attempt {attempt+1}: CDX fetch failed {status}', file=sys.stderr)
        time.sleep(5 * (attempt + 1))
    return None

def parse_cdx(text):
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        print('CDX response not JSON', file=sys.stderr)
        return {}
    header = data[0]
    idx_url = header.index('original') if 'original' in header else 0
    idx_ts = header.index('timestamp') if 'timestamp' in header else 1
    urls_by_date = {}
    seen = set()
    for row in data[1:]:
        url = row[idx_url]
        ts = row[idx_ts]
        try:
            dt = datetime.datetime.strptime(ts, '%Y%m%d%H%M%S')
        except ValueError:
            continue
        d = dt.date()
        if d < START or d > END:
            continue
        if url in seen:
            continue
        seen.add(url)
        urls_by_date.setdefault(d, []).append(url)
    return urls_by_date

cdx_text = fetch_cdx()
if cdx_text:
    urls_by_date = parse_cdx(cdx_text)
else:
    # Fallback: use site search for each day
    urls_by_date = {}
    seen = set()
    cur = START
    while cur <= END:
        query_url = f'https://tn.com.ar/?s={cur.isoformat()}'
        for attempt in range(3):
            status, page, _ = fetch(query_url)
            if status == 200:
                break
            print(f'Attempt {attempt+1}: search fetch failed {status}', file=sys.stderr)
            time.sleep(5 * (attempt + 1))
        else:
            cur += datetime.timedelta(days=1)
            continue
        # extract hrefs like /noticias/... and full URLs
        for path in re.findall(r'href\s*=\s*"(/[^\"]+)"', page):
            full = urljoin('https://tn.com.ar', path)
            # Keep only plausible article URLs (contain a year segment)
            if '/2026/' not in full:
                continue
            if full in seen:
                continue
            seen.add(full)
            # Try to get a date from meta tag if present in the page snippet
            m = re.search(r'<meta\s+property="article:published_time"\s+content="([0-9T:-]+)"', page)
            if m:
                try:
                    dt = datetime.datetime.fromisoformat(m.group(1).replace('Z','+00:00'))
                    d = dt.date()
                except ValueError:
                    d = cur
            else:
                d = cur
            urls_by_date.setdefault(d, []).append(full)
        cur += datetime.timedelta(days=1)

out_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../data/urls_custom'))
os.makedirs(out_dir, exist_ok=True)
out_path = os.path.join(out_dir, 'tn-com-ar.tsv')
with open(out_path, 'w', encoding='utf-8') as f:
    for d in sorted(urls_by_date):
        for u in urls_by_date[d]:
            f.write(f"{u}\t{d.isoformat()}\n")

# Print per‑day counts
for d in sorted(urls_by_date):
    print(f"{d.isoformat()}: {len(urls_by_date[d])} URLs")
