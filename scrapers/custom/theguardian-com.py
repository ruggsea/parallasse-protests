#!/usr/bin/env python3
import os, sys, re, datetime, calendar, xml.etree.ElementTree as ET
from urllib.parse import urljoin

# Ensure polite_fetch is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
try:
    from polite_fetch import fetch
except ImportError:
    print('polite_fetch not found', file=sys.stderr)
    sys.exit(1)

BASE = 'https://www.theguardian.com'
START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)
# Sections to query – world is the most comprehensive, add others for coverage
SECTIONS = ['world', 'sport', 'culture', 'technology', 'business', 'politics', 'environment']

def fetch_text(url):
    status, text, _ = fetch(url)
    if status != 200:
        print(f'Failed {status} fetching {url}', file=sys.stderr)
        return None
    return text

def collect_from_section(date: datetime.date, section: str):
    month_abbr = calendar.month_abbr[date.month].lower()
    url = f"{BASE}/{section}/{date.year}/{month_abbr}/{date.day:02d}/all"
    txt = fetch_text(url)
    if not txt:
        return []
    pattern = rf"/{section}/{date.year}/{month_abbr}/{date.day:02d}/"
    links = set(re.findall(r'href="(https://www\.theguardian\.com[^"]+)"', txt))
    return [l for l in links if re.search(pattern, l)]

def main():
    all_links = {}
    cur = START
    while cur <= END:
        for sec in SECTIONS:
            daily = collect_from_section(cur, sec)
            for link in daily:
                all_links[link] = cur.isoformat()
        cur += datetime.timedelta(days=1)
    # Write output TSV
    out_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom'))
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, 'theguardian-com.tsv')
    with open(out_path, 'w', encoding='utf-8') as f:
        for url, d in sorted(all_links.items()):
            f.write(f"{url}\t{d}\n")
    # Print per‑day counts
    counts = {}
    for d in all_links.values():
        counts[d] = counts.get(d, 0) + 1
    for day in sorted(counts):
        print(f"{day}\t{counts[day]}")

if __name__ == '__main__':
    main()
