#!/usr/bin/env python3
import sys, os, json, datetime, time
from urllib.parse import urljoin

# Ensure polite_fetch is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from polite_fetch import fetch

BASE_URL = 'https://www.expreso.ec'
OUTPUT_TSV = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'expreso-ec.tsv'))
START_DATE = datetime.date(2026, 9, 25)
END_DATE = datetime.date(2026, 10, 25)


def parse_sitemap(sitemap_url):
    status, text, _ = fetch(sitemap_url)
    if status != 200:
        print(f'Failed {status} {sitemap_url}', file=sys.stderr)
        return []
    from xml.etree import ElementTree as ET
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        print(f'XML parse error {e} for {sitemap_url}', file=sys.stderr)
        return []
    urls = []
    ns = {
        'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9',
        'news': 'http://www.google.com/schemas/sitemap-news/0.9'
    }
    for url in root.findall('.//sm:url', ns):
        loc_el = url.find('sm:loc', ns)
        pub_el = url.find('.//news:publication_date', ns)
        if loc_el is None:
            continue
        u = loc_el.text.strip()
        date = None
        if pub_el is not None and pub_el.text:
            date = pub_el.text.strip()[:10]
        else:
            lm = url.find('sm:lastmod', ns)
            if lm is not None and lm.text:
                date = lm.text.strip()[:10]
        urls.append((u, date))
    return urls


def parse_rss(feed_url):
    status, text, _ = fetch(feed_url)
    if status != 200:
        print(f'Failed RSS {status} {feed_url}', file=sys.stderr)
        return []
    from xml.etree import ElementTree as ET
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        print(f'RSS XML parse error {e} for {feed_url}', file=sys.stderr)
        return []
    items = []
    for item in root.findall('.//item'):
        link_el = item.find('link')
        date_el = item.find('pubDate')
        if link_el is None or date_el is None:
            continue
        u = link_el.text.strip()
        try:
            dt = datetime.datetime.strptime(date_el.text.strip(), '%a, %d %b %Y %H:%M:%S %z')
            date = dt.date().isoformat()
        except Exception:
            date = None
        items.append((u, date))
    return items


def main():
    # Gather URLs from Google News sitemap
    sitemap_urls = [urljoin(BASE_URL, '/sitemap-google-news.xml')]
    all_entries = []
    for sm in sitemap_urls:
        all_entries.extend(parse_sitemap(sm))
    # Also gather from RSS feeds listed in robots.txt
    robots_url = urljoin(BASE_URL, '/robots.txt')
    status, robots_txt, _ = fetch(robots_url)
    if status == 200:
        for line in robots_txt.splitlines():
            if line.lower().startswith('sitemap:') and '/rss/' in line:
                rss_url = line.split(':',1)[1].strip()
                all_entries.extend(parse_rss(rss_url))
    # Filter by target date range
    filtered = []
    for url, date_str in all_entries:
        if date_str:
            try:
                d = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                continue
            if START_DATE <= d <= END_DATE:
                filtered.append((url, d.isoformat()))
        else:
            filtered.append((url, None))
    # Deduplicate, preferring known dates
    uniq = {}
    for url, d in filtered:
        uniq[url] = d or uniq.get(url)
    # Write output (initial pass)
    os.makedirs(os.path.dirname(OUTPUT_TSV), exist_ok=True)
    with open(OUTPUT_TSV, 'w', encoding='utf-8') as out:
        for url, d in uniq.items():
            if d is None:
                status, page, _ = fetch(url)
                if status != 200:
                    continue
                import re
                m = re.search(r'"datePublished"\s*:\s*"(\d{4}-\d{2}-\d{2})', page)
                if not m:
                    m = re.search(r'article:published_time".*content="(\d{4}-\d{2}-\d{2})"', page)
                if m:
                    d = m.group(1)
                else:
                    continue
            out.write(f"{url}\t{d}\n")
    # Summary per day
    from collections import Counter
    cnt = Counter()
    for _, d in uniq.items():
        if d:
            cnt[d] += 1
    for day in sorted(cnt):
        print(f"{day}\t{cnt[day]}")
    # If low volume, fallback to Wayback CDX
    total = sum(cnt.values())
    if total < 45:
        print('Attempting Wayback CDX fallback per-day', file=sys.stderr)
        from datetime import timedelta
        day = START_DATE
        while day <= END_DATE:
            cdx_day = day.strftime('%Y%m%d')
            cdx_query = f"https://web.archive.org/cdx/search/cdx?url=expreso.ec/*&from={cdx_day}&to={cdx_day}&output=json&collapse=urlkey"
            try:
                import urllib.request, json, ssl
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                with urllib.request.urlopen(cdx_query, context=ctx) as f:
                    data = json.load(f)
                for row in data[1:]:
                    url = row[2]
                    timestamp = row[1]
                    d = datetime.datetime.strptime(timestamp[:8], '%Y%m%d').date()
                    if START_DATE <= d <= END_DATE:
                        uniq[url] = d.isoformat()
            except Exception as e:
                print(f'CDX day {cdx_day} failed: {e}', file=sys.stderr)
            day += timedelta(days=1)
        # Rewrite output with CDX results
        with open(OUTPUT_TSV, 'w', encoding='utf-8') as out:
            for url, d in uniq.items():
                out.write(f"{url}\t{d}\n")
        cnt = Counter()
        for _, d in uniq.items():
            if d:
                cnt[d] += 1
        for day in sorted(cnt):
            print(f"FINAL {day}\t{cnt[day]}")

if __name__ == '__main__':
    main()
