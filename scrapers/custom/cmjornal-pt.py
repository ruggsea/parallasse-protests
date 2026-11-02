#!/usr/bin/env python3
"""Scraper for Correio da Manhã (cmjornal.pt).
Collect article URLs published between 2026-09-25 and 2026-10-25 inclusive.
Outputs TSV at data/urls_custom/cmjornal-pt.tsv with columns: URL<TAB>YYYY-MM-DD.
Uses polite_fetch for all HTTP requests.
"""
import sys
import os
import re
import json
import datetime as dt
import xml.etree.ElementTree as ET
from urllib.parse import urljoin

# Ensure repo root is in path for polite_fetch
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../..", ".."))
sys.path.insert(0, os.path.join(repo_root, "scrapers"))
try:
    from polite_fetch import fetch
except Exception as e:
    sys.stderr.write(f"Failed to import polite_fetch: {e}\n")
    sys.exit(1)

START = dt.date(2026, 9, 25)
END = dt.date(2026, 10, 25)
OUT_TSV = os.path.abspath(os.path.join(repo_root, "data", "urls_custom", "cmjornal-pt.tsv"))
os.makedirs(os.path.dirname(OUT_TSV), exist_ok=True)

def parse_date(text):
    # Try ISO formats
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f%z"):
        try:
            return dt.datetime.strptime(text, fmt).date()
        except Exception:
            continue
    # Fallback: extract YYYY-MM-DD via regex
    m = re.search(r"(\d{4}-\d{2}-\d{2})", text)
    if m:
        return dt.datetime.strptime(m.group(1), "%Y-%m-%d").date()
    return None

def fetch_robots_sitemaps(base_url="https://www.cmjornal.pt"):
    status, txt, _ = fetch(base_url + "/robots.txt")
    if status != 200 or not txt:
        return []
    sitemaps = []
    for line in txt.splitlines():
        if line.lower().startswith("sitemap:"):
            s = line.split(":", 1)[1].strip()
            sitemaps.append(s)
    return sitemaps

def fetch_sitemap(url):
    status, txt, _ = fetch(url)
    if status != 200 or not txt:
        return []
    # Some sitemaps are gzipped; try to handle basic gzip header
    if txt[:2] == '\x1f\x8b':
        import gzip, io
        txt = gzip.GzipFile(fileobj=io.BytesIO(txt.encode('latin1'))).read().decode('utf-8', errors='ignore')
    try:
        root = ET.fromstring(txt)
    except ET.ParseError:
        return []
    ns = {'news': 'http://www.google.com/schemas/sitemap-news/0.9'}
    entries = []
    for url_el in root.findall('.//{*}url'):
        loc = url_el.find('{*}loc')
        if loc is None or not loc.text:
            continue
        url = loc.text.strip()
        # Prefer news:publication_date
        pub_date_el = url_el.find('.//news:publication_date', ns)
        if pub_date_el is not None and pub_date_el.text:
            d = parse_date(pub_date_el.text.strip())
        else:
            lastmod = url_el.find('{*}lastmod')
            d = parse_date(lastmod.text.strip()) if lastmod is not None else None
        if d:
            entries.append((url, d))
    return entries

def fetch_wayback_cdx(start, end):
    # CDX API returns JSON lines: ["timestamp","original","..."]
    base = "https://web.archive.org/cdx/search/cdx"
    params = (
        f"url=www.cmjornal.pt/*&from={start:%Y%m%d}&to={end:%Y%m%d}&output=json&collapse=urlkey"
    )
    url = f"{base}?{params}"
    status, txt, _ = fetch(url)
    if status != 200 or not txt:
        return []
    try:
        rows = json.loads(txt)
    except Exception:
        return []
    # first row is header
    entries = []
    for row in rows[1:]:
        timestamp, original = row[1], row[2]
        try:
            d = dt.datetime.strptime(timestamp[:8], "%Y%m%d").date()
        except Exception:
            continue
        entries.append((original, d))
    return entries

def main():
    entries = []
    # 1) Try sitemaps from robots.txt
    sitemaps = fetch_robots_sitemaps()
    for sm in sitemaps:
        # If sitemap is an index, fetch it and recurse
        if sm.endswith('.xml'):
            entries.extend(fetch_sitemap(sm))
        else:
            # fallback: try as is
            entries.extend(fetch_sitemap(sm))
    # If we have insufficient entries for any day, fallback to Wayback
    need_fallback = False
    # Build dict per date count
    counts = {}
    for _, d in entries:
        if START <= d <= END:
            counts[d] = counts.get(d, 0) + 1
    for day in (START + dt.timedelta(days=i) for i in range((END-START).days+1)):
        if counts.get(day, 0) < 15:
            need_fallback = True
            break
    if need_fallback:
        entries.extend(fetch_wayback_cdx(START, END))
    # Filter and dedupe
    uniq = {}
    for url, d in entries:
        if d < START or d > END:
            continue
        uniq[url] = d  # latest date wins if duplicate
    # Write TSV sorted by date then url
    with open(OUT_TSV, "w", encoding="utf-8") as f:
        for url, d in sorted(uniq.items(), key=lambda x: (x[1], x[0])):
            f.write(f"{url}\t{d.isoformat()}\n")
    # Print per‑day count
    per_day = {}
    for d in uniq.values():
        per_day[d] = per_day.get(d, 0) + 1
    for day in sorted(per_day):
        print(f"{day}: {per_day[day]} URLs")

if __name__ == "__main__":
    main()
