#!/usr/bin/env python3
import sys, os, datetime, json, time, xml.etree.ElementTree as ET

# Make polite_fetch importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from polite_fetch import fetch
except ImportError:
    print('polite_fetch not found', file=sys.stderr)
    sys.exit(1)

# Primary source: AU Atom feed (latest only)
FEED_URL = 'https://theconversation.com/au/articles?sort=latest&page={page}'
# News sitemap (contains publication_date)
BASE_SITEMAP = 'https://theconversation.com/au/sitemap_news.xml'
# Wayback CDX fallback (capture timestamps used as dates)
CDX_URL = ('https://web.archive.org/cdx/search/cdx?url=theconversation.com/*'
           '&from=20260925&to=20261025&output=json&collapse=urlkey')

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

def iso_to_date(s: str) -> datetime.date | None:
    try:
        dt = datetime.datetime.fromisoformat(s.replace('Z', '+00:00'))
        return dt.date()
    except Exception:
        return None

def cdx_ts_to_date(ts: str) -> datetime.date | None:
    try:
        return datetime.datetime.strptime(ts[:8], '%Y%m%d').date()
    except Exception:
        return None

def fetch_url(url: str, retries: int = 1, delay: int = 5) -> str | None:
    for attempt in range(retries):
        status, text, _ = fetch(url)
        if status == 200:
            return text
        print(f'Fetch {url} failed (status {status}); attempt {attempt + 1}/{retries}', file=sys.stderr)
        if attempt < retries - 1:
            time.sleep(delay)
    return None

def parse_atom(page: int):
    url = FEED_URL.format(page=page)
    txt = fetch_url(url)
    if not txt:
        return []
    root = ET.fromstring(txt)
    ns = {'atom': 'http://www.w3.org/2005/Atom'}
    entries = []
    for entry in root.findall('atom:entry', ns):
        link_el = entry.find('atom:link', ns)
        pub_el = entry.find('atom:published', ns)
        if link_el is None or pub_el is None:
            continue
        article_url = link_el.attrib.get('href')
        pub_date = iso_to_date(pub_el.text.strip())
        if article_url and pub_date and START <= pub_date <= END:
            entries.append((article_url, pub_date.isoformat()))
    return entries

def parse_news_sitemap(xml_text: str):
    ns = {
        'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9',
        'news': 'http://www.google.com/schemas/sitemap-news/0.9'
    }
    root = ET.fromstring(xml_text)
    for url_el in root.findall('ns:url', ns):
        loc = url_el.find('ns:loc', ns)
        pub = url_el.find('news:news/news:publication_date', ns)
        if loc is None or pub is None:
            continue
        url = loc.text.strip()
        pub_date = iso_to_date(pub.text.strip())
        if pub_date and START <= pub_date <= END:
            yield url, pub_date.isoformat()

def parse_cdx(json_text: str):
    try:
        data = json.loads(json_text)
    except Exception as e:
        print('CDX JSON parse error:', e, file=sys.stderr)
        return []
    if not data or not isinstance(data[0], list):
        return []
    fields = data[0]
    url_idx = fields.index('url') if 'url' in fields else 1
    ts_idx = fields.index('timestamp') if 'timestamp' in fields else 1
    results = []
    for row in data[1:]:
        url = row[url_idx]
        ts = row[ts_idx]
        date = cdx_ts_to_date(ts)
        if date and START <= date <= END:
            results.append((url, date.isoformat()))
    return results

def collect_entries():
    entries = []
    # 1. Atom feed (only recent)
    page = 1
    while True:
        page_entries = parse_atom(page)
        if not page_entries:
            break
        entries.extend(page_entries)
        dates = [datetime.date.fromisoformat(d) for _, d in page_entries]
        if min(dates) < START:
            break
        page += 1
        if page > 200:
            break
    # 2. News sitemap if needed
    needed = {'2026-09-30', '2026-10-10', '2026-10-20'}
    per_day = {}
    for u, d in entries:
        per_day.setdefault(d, set()).add(u)
    need_fallback = any(len(per_day.get(d, [])) < 15 for d in needed)
    if need_fallback:
        xml = fetch_url(BASE_SITEMAP)
        if xml:
            entries.extend(list(parse_news_sitemap(xml)))
    # 3. CDX fallback with retries
    per_day = {}
    for u, d in entries:
        per_day.setdefault(d, set()).add(u)
    need_cdx = any(len(per_day.get(d, [])) < 15 for d in needed)
    if need_cdx:
        cdx_json = fetch_url(CDX_URL, retries=5, delay=10)
        if cdx_json:
            entries.extend(parse_cdx(cdx_json))
    return entries

def main():
    entries = collect_entries()
    seen = set()
    final = {}
    for url, date in entries:
        if url in seen:
            continue
        seen.add(url)
        final.setdefault(date, []).append(url)
    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'theconversation-com.tsv'))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        for date in sorted(final):
            for url in sorted(set(final[date])):
                f.write(f"{url}\t{date}\n")
    total = 0
    for date in sorted(final):
        cnt = len(set(final[date]))
        total += cnt
        print(f"{date}: {cnt} URLs")
    print(f"Total URLs: {total}")

if __name__ == '__main__':
    main()
