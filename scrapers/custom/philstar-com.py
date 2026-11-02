#!/usr/bin/env python3
"""Scrape article URLs from The Philippine Star (philstar.com) for a given date range.

The script follows the site’s robots.txt (via polite_fetch) and extracts URLs that embed
a publication date in the path, e.g.:
    https://www.philstar.com/headlines/2026/10/26/2565825/old-playbook-vs-duterte-critics-resurfaces-journalist-philip-lustres-arrest
The date components (year/month/day) are taken from the URL because the sitemap does not
provide reliable <lastmod> values.

Output:
  data/urls_custom/philstar-com.tsv – tab‑separated URL and ISO date (YYYY‑MM‑DD),
  one line per unique article.

A JSON part‑file is also written with notes about the run (used by the grid manager).
"""
import os
import re
import sys
import datetime
import xml.etree.ElementTree as ET
from collections import defaultdict

# Ensure the project’s scraper path is on sys.path for polite_fetch
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from polite_fetch import fetch
except Exception as e:
    sys.stderr.write(f"Failed to import polite_fetch: {e}\n")
    sys.exit(1)

# Configuration --------------------------------------------------------------
START_DATE = datetime.date(2026, 9, 25)
END_DATE   = datetime.date(2026, 10, 25)

# Output locations (relative to project root)
TSV_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'philstar-com.tsv'))
NOTE_JSON = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'grids', 'custom', 'out', 'philstar-com.json.part'))

# ---------------------------------------------------------------------------

def iso(date_obj: datetime.date) -> str:
    return date_obj.isoformat()

def date_from_url(url: str) -> datetime.date | None:
    """Extract a date from a URL containing /YYYY/MM/DD/.
    Returns a date object or None if pattern not found.
    """
    m = re.search(r"/(\d{4})/(\d{2})/(\d{2})/", url)
    if not m:
        return None
    try:
        return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None

def fetch_section_urls(section_url: str) -> set[str]:
    """Fetch a section with pagination ("?page=N") and collect article URLs.
    The function walks pages until a page yields no new URLs within the date range
    (or a non‑200 response). A safety limit of 200 pages prevents endless loops.
    """
    result: set[str] = set()
    page = 1
    while True:
        paged_url = f"{section_url}?page={page}" if page > 1 else section_url
        status, html, _ = fetch(paged_url)
        if status != 200 or not html:
            break
        # Extract all links to the same domain
        links = set(re.findall(r"href=\"(https?://www\.philstar\.com[^\"']+)\"", html))
        added_this_page = 0
        for u in links:
            d = date_from_url(u)
            if d and START_DATE <= d <= END_DATE:
                norm = u.rstrip('/')
                if norm not in result:
                    result.add(norm)
                    added_this_page += 1
        # Continue paging even if this page adds no URLs – older pages may still contain dates within the range.
        # The loop will stop when the response is non‑200 or when the safety limit is reached.
        # (No early break based on added_this_page)
        page += 1
        if page > 200:
            break
    return result

def main():
    # 1. Load sitemap index to discover section URLs
    sitemap_url = 'https://www.philstar.com/sitemap.xml'
    status, sitemap_xml, _ = fetch(sitemap_url)
    if status != 200:
        sys.stderr.write(f"Failed to fetch sitemap {sitemap_url}, status {status}\n")
        sys.exit(1)
    try:
        root = ET.fromstring(sitemap_xml)
    except ET.ParseError as e:
        sys.stderr.write(f"Error parsing sitemap XML: {e}\n")
        sys.exit(1)
    ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    section_urls = [elem.find('ns:loc', ns).text for elem in root.findall('ns:url', ns) if elem.find('ns:loc', ns) is not None]

    all_urls = set()
    for sec in section_urls:
        urls = fetch_section_urls(sec)
        all_urls.update(urls)

    # 2. Write TSV
    os.makedirs(os.path.dirname(TSV_PATH), exist_ok=True)
    with open(TSV_PATH, 'w', encoding='utf-8') as out_f:
        # Group by date for reporting
        per_day = defaultdict(list)
        for u in sorted(all_urls):
            d = date_from_url(u)
            if not d:
                continue
            per_day[d].append(u)
            out_f.write(f"{u}\t{iso(d)}\n")
    # 3. Print summary
    total = len(all_urls)
    sys.stdout.write(f"Wrote {total} URLs to {TSV_PATH}\n")
    for d in sorted(per_day):
        sys.stdout.write(f"{iso(d)}: {len(per_day[d])} URLs\n")

    # 4. Write notes JSON (used by the grid manager)
    notes = {
        "script": os.path.relpath(__file__, start=os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))),
        "notes": f"Fetched sitemap, visited {len(section_urls)} sections, collected {total} URLs within range."
    }
    import json
    os.makedirs(os.path.dirname(NOTE_JSON), exist_ok=True)
    with open(NOTE_JSON, 'w', encoding='utf-8') as jf:
        json.dump(notes, jf)

if __name__ == '__main__':
    main()
