#!/usr/bin/env python3
"""Scrape Vancouver Sun article URLs for a date range.

The script respects robots.txt (the sitemap URLs are allowed) and uses the
polite_fetch.fetch helper for rate‑limited HTTP access.
It iterates over each day in the target window, requests the date‑specific
story sitemap (e.g. ``sitemap-story.xml?y=2026&m=09&d=25``), extracts ``<loc>``
and ``<lastmod>`` entries, filters by the requested window, deduplicates URLs
and writes ``URL<TAB>YYYY‑MM‑DD`` lines to ``data/urls_custom/vancouversun-com.tsv``.
Finally it prints per‑day counts.
"""
import sys, os, datetime, xml.etree.ElementTree as ET
from collections import Counter

# Make the repository root importable so ``polite_fetch`` can be found.
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
# Add the scrapers package to the import path where polite_fetch lives
scrapers_path = os.path.join(repo_root, "scrapers")
sys.path.insert(0, scrapers_path)
try:
    from polite_fetch import fetch
except ImportError:
    print("polite_fetch not found", file=sys.stderr)
    sys.exit(1)

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

def fetch_sitemap_for(date: datetime.date):
    """Return the raw XML of the story sitemap for *date*.

    The site provides per‑day sitemaps at
    ``https://vancouversun.com/sitemap-story.xml?y=YYYY&m=MM&d=DD``.
    """
    url = (
        f"https://vancouversun.com/sitemap-story.xml?y={date.year}&m={date.month:02d}&d={date.day:02d}"
    )
    status, text, _ = fetch(url)
    if status != 200:
        print(f"Failed to fetch {url}: status {status}", file=sys.stderr)
        return None
    return text

all_entries = []
current = START
while current <= END:
    xml_text = fetch_sitemap_for(current)
    if xml_text:
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as e:
            print(f"XML parse error for {current}: {e}", file=sys.stderr)
            current += datetime.timedelta(days=1)
            continue
        # Detect namespace usage
        ns = {}
        if root.tag.startswith('{'):
            uri = root.tag.split('}')[0].strip('{')
            ns = {"ns": uri}
            url_elems = root.findall('ns:url', ns)
        else:
            url_elems = root.findall('url')
        for url_elem in url_elems:
            loc = (
                url_elem.find('ns:loc', ns) if ns else url_elem.find('loc')
            )
            lastmod = (
                url_elem.find('ns:lastmod', ns) if ns else url_elem.find('lastmod')
            )
            if loc is None or lastmod is None:
                continue
            url = loc.text.strip()
            date_part = lastmod.text.strip()[:10]
            all_entries.append((url, date_part))
    current += datetime.timedelta(days=1)

# Deduplicate while preserving order
seen = set()
unique = []
for url, d in all_entries:
    if url not in seen:
        seen.add(url)
        unique.append((url, d))

out_path = os.path.abspath(os.path.join(repo_root, "data", "urls_custom", "vancouversun-com.tsv"))
os.makedirs(os.path.dirname(out_path), exist_ok=True)
with open(out_path, "w", encoding="utf-8") as f:
    for url, d in unique:
        f.write(f"{url}\t{d}\n")

# Report per‑day counts
cnt = Counter(d for _, d in unique)
for day in sorted(cnt):
    print(f"{day}\t{cnt[day]}")

print(f"Wrote {len(unique)} URLs to {out_path}")
