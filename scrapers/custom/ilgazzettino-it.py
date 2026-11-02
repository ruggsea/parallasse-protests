#!/usr/bin/env python3

"""Scrape article URLs from Il Gazzettino (ilgazzettino.it) for the date range
2026-09-25 to 2026-10-25.

The site advertises a news sitemap in robots.txt, but it only contains recent
articles. To guarantee coverage for every day in the window we fall back to the
per‑day archive pages (e.g. https://www.ilgazzettino.it/archivio/2026/09/30/).
Each archive page lists article links; we extract URLs ending in ``.html`` and
exclude video URLs. The script deduplicates URLs, records the date of the archive
page (which matches the publication date for most items), and writes a TSV:
    URL<TAB>YYYY-MM-DD
No header, one line per unique URL.
"""

import os
import sys
import datetime
import re
import xml.etree.ElementTree as ET

# Make the project's helper directory importable for ``polite_fetch``.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
try:
    from polite_fetch import fetch
except Exception as e:
    print("Failed to import polite_fetch:", e, file=sys.stderr)
    sys.exit(1)

SITEMAP_URL = "https://www.ilgazzettino.it/?sez=XML&p=MapNews"
OUTPUT_TSV = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "urls_custom", "ilgazzettino-it.tsv"))
START_DATE = datetime.date(2026, 9, 25)
END_DATE = datetime.date(2026, 10, 25)

def fetch_sitemap(url: str) -> str:
    status, text, _ = fetch(url)
    if status != 200:
        raise RuntimeError(f"Failed to fetch sitemap {url}: HTTP {status}")
    return text

def parse_sitemap(xml_content: str):
    ns = {
        'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9',
        'news': 'http://www.google.com/schemas/sitemap-news/0.9',
    }
    root = ET.fromstring(xml_content)
    for url_el in root.findall('ns:url', ns):
        loc_el = url_el.find('ns:loc', ns)
        pubdate_el = url_el.find('news:news/news:publication_date', ns)
        if loc_el is None or pubdate_el is None:
            continue
        url = loc_el.text.strip()
        pubdate_str = pubdate_el.text.strip()
        try:
            pub_dt = datetime.datetime.fromisoformat(pubdate_str)
        except Exception:
            pub_dt = datetime.datetime.strptime(pubdate_str[:19], "%Y-%m-%dT%H:%M:%S")
        pub_date = pub_dt.date()
        if START_DATE <= pub_date <= END_DATE:
            yield url, pub_date

def fetch_archive_for_date(date: datetime.date):
    archive_url = f"https://www.ilgazzettino.it/archivio/{date.year:04d}/{date.month:02d}/{date.day:02d}/"
    status, text, _ = fetch(archive_url)
    if status != 200:
        return []
    links = re.findall(r'https?://[^"\'>]+\\.html', text)
    # Remove video URLs and deduplicate locally
    filtered = {ln for ln in links if '/video/' not in ln}
    return [(ln, date) for ln in filtered]

def main():
    entries = []
    # Try the sitemap first – it is fast and gives correct publication dates.
    try:
        xml = fetch_sitemap(SITEMAP_URL)
        entries.extend(list(parse_sitemap(xml)))
    except Exception as e:
        print(f"Sitemap error: {e}", file=sys.stderr)

    # Determine which dates are missing and fetch their archive pages.
    covered = {d for _, d in entries}
    cur = START_DATE
    while cur <= END_DATE:
        if cur not in covered:
            entries.extend(fetch_archive_for_date(cur))
        cur += datetime.timedelta(days=1)

    # Global deduplication – keep the first encountered date.
    unique = {}
    for url, d in entries:
        if url not in unique:
            unique[url] = d

    os.makedirs(os.path.dirname(OUTPUT_TSV), exist_ok=True)
    with open(OUTPUT_TSV, "w", encoding="utf-8") as out:
        for url, d in sorted(unique.items(), key=lambda x: (x[1], x[0])):
            out.write(f"{url}\t{d.isoformat()}\n")

    from collections import Counter
    day_counts = Counter(d.isoformat() for d in unique.values())
    for day in sorted(day_counts):
        print(f"{day}\t{day_counts[day]}")
    print(f"Wrote {len(unique)} URLs to {OUTPUT_TSV}")

if __name__ == "__main__":
    main()
