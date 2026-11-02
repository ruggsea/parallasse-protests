#!/usr/bin/env python3
import sys, os, re, json, time
from datetime import datetime, timezone, timedelta

# Ensure import path for polite_fetch
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from polite_fetch import fetch
except Exception as e:
    sys.stderr.write(f'Failed to import polite_fetch: {e}\n')
    sys.exit(1)

BASE = 'https://ojo-publico.com'
OUT_TSV = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'ojo-publico-com.tsv'))
START = datetime(2026, 9, 25, tzinfo=timezone(timedelta(hours=-5)))  # Peru UTC-5
END = datetime(2026, 10, 25, 23, 59, 59, tzinfo=timezone(timedelta(hours=-5)))

def parse_date(text):
    """Parse date from meta tag or JSON-LD string to datetime with timezone -5."""
    # meta example: "Jue, 27/08/2026 - 18:33"
    m = re.search(r'\b(\d{2}/\d{2}/\d{4})\b', text)
    if m:
        try:
            dt = datetime.strptime(m.group(1), '%d/%m/%Y')
            return dt.replace(tzinfo=timezone(timedelta(hours=-5)))
        except ValueError:
            pass
    # ISO format e.g., 2026-08-27T18:33:36-05:00
    m = re.search(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})([+-]\d{2}:?\d{2})?', text)
    if m:
        try:
            dt = datetime.fromisoformat(m.group(0))
            return dt
        except Exception:
            pass
    return None

def extract_date_from_article(url):
    status, txt, _ = fetch(url)
    if status != 200:
        return None
    # Try meta property
    m = re.search(r'<meta[^>]+property="article:published_time"[^>]+content="([^"]+)"', txt)
    if m:
        dt = parse_date(m.group(1))
        if dt:
            return dt
    # Try JSON-LD datePublished
    m = re.search(r'"datePublished"\s*:\s*"([^"]+)"', txt)
    if m:
        dt = parse_date(m.group(1))
        if dt:
            return dt
    return None

def fetch_wayback():
    cdn = f'http://web.archive.org/cdx/search/cdx?url=ojo-publico.com/*&from=20260925&to=20261025&output=json&collapse=urlkey'
    status, txt, _ = fetch(cdn)
    if status != 200:
        return []
    try:
        data = json.loads(txt)
    except Exception:
        return []
    # first row is header
    urls = [row[2] for row in data[1:] if len(row) > 2]
    return urls

def fetch_sitemap_urls():
    """Fetch URLs and their lastmod dates from the paginated sitemap.
    Returns list of (url, lastmod_str) tuples.
    """
    results = []
    page = 1
    while True:
        sitemap = f'{BASE}/sitemap.xml?page={page}'
        status, txt, _ = fetch(sitemap)
        if status != 200:
            break
        # extract <url> blocks
        entries = re.findall(r'<url>\s*<loc>(https?://[^<]+)</loc>\s*<lastmod>([^<]+)</lastmod>', txt)
        if not entries:
            # maybe no more entries
            break
        for loc, lastmod in entries:
            results.append((loc, lastmod))
        page += 1
        if page > 1000:
            break
        time.sleep(1)  # be gentle
    return results

def main():
    seen = set()
    results = []
    # Try Wayback first
    cd_urls = fetch_wayback()
    if cd_urls:
        source = 'wayback'
        candidate = [(u, None) for u in cd_urls]  # dates unknown, will fetch later
    else:
        source = 'sitemap'
        candidate = fetch_sitemap_urls()
    for url, lastmod_str in candidate:
        if url in seen:
            continue
        # Prefer lastmod from sitemap if available
        dt = None
        if lastmod_str:
            dt = parse_date(lastmod_str)
        if not dt:
            dt = extract_date_from_article(url)
        if not dt:
            continue
        if START <= dt <= END:
            seen.add(url)
            results.append((url, dt.date().isoformat()))
        # throttling per host
        time.sleep(0.5)
    # write output TSV
    os.makedirs(os.path.dirname(OUT_TSV), exist_ok=True)
    with open(OUT_TSV, 'w', encoding='utf-8') as f:
        for u, d in results:
            f.write(f"{u}\t{d}\n")
    # summary
    per_day = {}
    for _, d in results:
        per_day.setdefault(d, 0)
        per_day[d] += 1
    for day in sorted(per_day):
        print(f"{day}: {per_day[day]} URLs")
    print(f"Total {len(results)} URLs written to {OUT_TSV} (source={source})")

if __name__ == '__main__':
    main()
