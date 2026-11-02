#!/usr/bin/env python3
"""Scrape Metro Ecuador article URLs for 2026-09-25 to 2026-10-25.
Writes TSV to data/urls_custom/metroecuador-com-ec.tsv with columns:
URL<TAB>YYYY-MM-DD (publication date from sitemap <lastmod>).
Uses polite_fetch (respect robots, rate‑limits).
"""
import sys
import os
import datetime
import xml.etree.ElementTree as ET

# Ensure the repo's scraper path is on sys.path for polite_fetch
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from polite_fetch import fetch

START = datetime.date(2026, 9, 25)
END   = datetime.date(2026, 10, 25)
BASE_SITEMAP = "https://www.metroecuador.com.ec/arc/outboundfeeds/sitemap/{date}?outputType=xml"

out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'metroecuador-com-ec.tsv'))
os.makedirs(os.path.dirname(out_path), exist_ok=True)

url_date = {}
day_counts = {}

def fetch_sitemap(date_str):
    url = BASE_SITEMAP.format(date=date_str)
    status, txt, _ = fetch(url)
    if status != 200:
        print(f"[WARN] Sitemap {url} returned status {status}", file=sys.stderr)
        return None
    return txt

cur = START
while cur <= END:
    date_str = cur.isoformat()
    txt = fetch_sitemap(date_str)
    if txt:
        try:
            root = ET.fromstring(txt)
        except ET.ParseError as e:
            print(f"[ERROR] XML parse failed for {date_str}: {e}", file=sys.stderr)
            cur += datetime.timedelta(days=1)
            continue
        # The XML uses a default namespace; we iterate over all elements and match tag endings.
        for url_el in root.iter():
            if not url_el.tag.endswith('url'):
                continue
            loc_el = None
            lastmod_el = None
            for child in url_el:
                if child.tag.endswith('loc'):
                    loc_el = child
                elif child.tag.endswith('lastmod'):
                    lastmod_el = child
            if loc_el is None or lastmod_el is None:
                continue
            url = loc_el.text.strip()
            lastmod = lastmod_el.text.strip()
            # Extract date part (YYYY-MM-DD) from lastmod (ISO format with time)
            pub_date = lastmod.split('T')[0]
            # Try to parse ISO date; if fails, fall back to date from URL path.
            pd = None
            try:
                pd = datetime.date.fromisoformat(pub_date)
            except ValueError:
                pass
            # If parsed date out of range or not parsed, extract from URL path.
            if pd is None or not (START <= pd <= END):
                import re
                m = re.search(r"/(\d{4})/(\d{2})/(\d{2})/", url)
                if m:
                    y, mth, d = m.groups()
                    try:
                        pd = datetime.date(int(y), int(mth), int(d))
                        pub_date = pd.isoformat()
                    except ValueError:
                        pd = None
            if pd and START <= pd <= END:
                url_date[url] = pub_date
                day_counts[pd] = day_counts.get(pd, 0) + 1
            # polite_fetch already rate‑limits per host
    else:
        print(f"[WARN] No sitemap for {date_str}", file=sys.stderr)
    cur += datetime.timedelta(days=1)

# ---------------------------------------------------------------------------
# Additional source: Google News RSS feed (contains recent items, may fill sparse days)
rss_url = 'https://www.metroecuador.com.ec/arc/outboundfeeds/google-news-feed/?outputType=xml'
status, rss_txt, _ = fetch(rss_url)
if status == 200:
    try:
        rss_root = ET.fromstring(rss_txt)
        for item in rss_root.iter():
            if not item.tag.endswith('item'):
                continue
            link_el = None
            pub_el = None
            for child in item:
                if child.tag.endswith('link'):
                    link_el = child
                elif child.tag.endswith('pubDate'):
                    pub_el = child
            if link_el is None or pub_el is None:
                continue
            url = link_el.text.strip()
            pub_str = pub_el.text.strip()
            # Parse RFC822 date
            try:
                from email.utils import parsedate_to_datetime
                dt = parsedate_to_datetime(pub_str)
                pub_date = dt.date().isoformat()
            except Exception:
                continue
            if START <= dt.date() <= END:
                # Prefer existing date from sitemap if present
                if url not in url_date:
                    url_date[url] = pub_date
                    day_counts[dt.date()] = day_counts.get(dt.date(), 0) + 1
    except ET.ParseError as e:
        print(f"[ERROR] RSS XML parse error: {e}", file=sys.stderr)
else:
    print(f"[WARN] Failed to fetch RSS feed ({status})", file=sys.stderr)

# Write TSV, unique URLs only
with open(out_path, 'w', encoding='utf-8') as f:
    for url, d in sorted(url_date.items()):
        f.write(f"{url}\t{d}\n")

# Print per‑day summary
print('URL counts per day:')
for d in sorted(day_counts):
    print(f"{d}: {day_counts[d]}")
