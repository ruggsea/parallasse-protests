#!/usr/bin/env python3
"""List abante.com.ph articles published 2026-09-25..2026-10-25.

Route: permissive robots.txt (Allow: /) -> /sitemap.xml (AIOSEO index) ->
post-sitemapN.xml files, newest-first. Article URLs carry the publication
date in the path: /YYYY/MM/DD/slug/. We walk the post-sitemap files in
index order and stop once a file's oldest date falls below the window
start (files are strictly descending by date). If the WAF leaves a window
day empty, a WP REST API pass over the window fills it.
"""
import os
import re
import sys
import time
import datetime
import json
import xml.etree.ElementTree as ET
from collections import defaultdict

sys.path.insert(0, 'scrapers')
from polite_fetch import fetch

BASE = 'https://www.abante.com.ph'
START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)
OUT = 'data/urls_custom/abante-com-ph.tsv'

DATE_PATH = re.compile(r'abante\.com\.ph/(\d{4})/(\d{2})/(\d{2})/')


def daterange(start, end):
    for n in range((end - start).days + 1):
        yield start + datetime.timedelta(n)


def fetch_xml(url, retries=3):
    for attempt in range(retries):
        status, text, _ = fetch(url)
        if status == 200:
            return text
        print(f'  {url} -> {status} ({len(text or "")} bytes), attempt {attempt + 1}', file=sys.stderr)
        if attempt + 1 < retries:
            time.sleep(4 * (attempt + 1))
    return None


def parse_urlset(text):
    """Return list of (loc, date|None) from a sitemap urlset (CDATA-safe)."""
    out = []
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        print(f'  XML parse error: {e}', file=sys.stderr)
        return out
    for url in root.iter('{http://www.sitemaps.org/schemas/sitemap/0.9}url'):
        loc = url.find('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
        if loc is None or not loc.text:
            continue
        loc = loc.text.strip()
        m = DATE_PATH.search(loc)
        d = None
        if m:
            d = datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        out.append((loc, d))
    return out


def main():
    # 1. Sitemap index -> ordered list of post-sitemap files
    index = fetch_xml(BASE + '/sitemap.xml')
    post_maps = []
    if index:
        root = ET.fromstring(index)
        for sm in root.iter('{http://www.sitemaps.org/schemas/sitemap/0.9}sitemap'):
            loc = sm.find('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
            if loc is not None and loc.text:
                loc = loc.text.strip()
                if re.search(r'/post-sitemap\d*\.xml', loc):
                    post_maps.append(loc)
    if not post_maps:
        # fallback: well-known names in canonical order
        post_maps = [BASE + '/post-sitemap.xml'] + [
            f'{BASE}/post-sitemap{i}.xml' for i in range(2, 12)
        ]
    print(f'post-sitemaps to walk: {len(post_maps)}')

    entries = []  # (url, date)
    for sm_url in post_maps[:12]:  # hard cap on requests
        print(f'fetching {sm_url}')
        text = fetch_xml(sm_url)
        if text is None:
            continue
        items = parse_urlset(text)
        dated = [d for _, d in items if d is not None]
        if not dated:
            continue
        print(f'  {len(items)} urls, newest {max(dated)}, oldest {min(dated)}')
        entries.extend((u, d) for u, d in items if d is not None)
        # files are strictly descending; once one reaches below the window
        # start, every later file is older -> stop.
        if min(dated) < START:
            break

    # 2. Filter to window, dedupe
    seen = set()
    per_day = defaultdict(list)
    for url, d in entries:
        if d is None or not (START <= d <= END):
            continue
        if url in seen:
            continue
        seen.add(url)
        per_day[d].append(url)

    # 3. Fallback for any window day the sitemaps left empty (WAF 202 on a
    # file): WP REST API, one pass over the window, site-local 'date'.
    empty_days = sorted(d for d in daterange(START, END) if d not in per_day)
    if empty_days:
        print(f'sitemap walk left empty days {empty_days} -> REST fallback')
        after = (START - datetime.timedelta(days=1)).isoformat() + 'T00:00:00'
        before = (END + datetime.timedelta(days=1)).isoformat() + 'T23:59:59'
        page = 1
        while page <= 20 and empty_days:
            ru = (f'{BASE}/wp-json/wp/v2/posts?per_page=100&_fields=link,date'
                  f'&after={after}&before={before}&page={page}')
            status, text, _ = fetch(ru)
            if status != 200 or not text:
                print(f'  REST -> {status}', file=sys.stderr)
                break
            try:
                rows = json.loads(text)
            except Exception as e:
                print(f'  REST json error: {e}', file=sys.stderr)
                break
            if not isinstance(rows, list) or not rows:
                break
            oldest_empty = empty_days[0]
            stop = False
            for row in rows:
                d = datetime.date.fromisoformat(row['date'][:10])
                if d < oldest_empty:
                    stop = True
                    break
                if not (START <= d <= END) or row['link'] in seen:
                    continue
                seen.add(row['link'])
                per_day[d].append(row['link'])
                if d in empty_days:
                    empty_days.remove(d)
            if stop or len(rows) < 100:
                break
            page += 1
            time.sleep(1)

    # 4. Write TSV
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    total = 0
    with open(OUT, 'w', encoding='utf-8') as f:
        for day in sorted(per_day):
            for u in sorted(per_day[day]):
                f.write(f'{u}\t{day.isoformat()}\n')
                total += 1
    for day in sorted(per_day):
        print(f'{day}: {len(per_day[day])} URLs')
    print(f'Total URLs written: {total}')


if __name__ == '__main__':
    main()
