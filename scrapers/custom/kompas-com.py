#!/usr/bin/env python3
"""List article URLs published by Kompas.com (Indonesia) from 2026-09-25 to 2026-10-25.
Route: sitemap index (https://www.kompas.com/sitemap.xml) lists several news sitemaps.
Each news sitemap contains <url><loc>URL</loc><news:news><news:publication_date>ISO</news:publication_date></news:news></url>.
We fetch each sitemap via the polite_fetch helper, parse XML, keep entries whose publication_date falls within the target window.
Output: data/urls_custom/kompas-com.tsv – one line URL<TAB>YYYY-MM-DD, no header, unique URLs, sorted by date then URL.
Prints per‑day counts to stderr.
"""

import os
import sys
import time
import json
import xml.etree.ElementTree as ET

# Ensure the polite_fetch helper is on sys.path
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scrapers"))
from polite_fetch import fetch  # noqa: E402

BASE = "https://www.kompas.com"
SITEMAP_INDEX = f"{BASE}/sitemap.xml"
TARGET_START = "2026-09-25"
TARGET_END = "2026-10-25"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "urls_custom", "kompas-com.tsv")


def fetch_xml(url, retries=3):
    """Fetch a URL with polite_fetch and return parsed ElementTree or None."""
    for attempt in range(1, retries + 1):
        status, text, _ = fetch(url)
        if status == 200 and text:
            try:
                return ET.fromstring(text)
            except ET.ParseError as e:
                print(f"Parse error {e} on {url}", file=sys.stderr)
                status = 0
        print(f"  fetch status={status} attempt={attempt}/{retries} {url}", file=sys.stderr)
        if attempt < retries:
            time.sleep(5 * attempt)
    return None


def iso_to_date(iso_str):
    """Convert ISO datetime like 2026-10-25T21:00:00+07:00 to YYYY-MM-DD string."""
    return iso_str.split("T")[0]


def main():
    # Step 1: fetch sitemap index
    root = fetch_xml(SITEMAP_INDEX)
    if root is None:
        sys.exit(f"ERROR: cannot fetch sitemap index {SITEMAP_INDEX}")

    # Namespace handling
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    # Some sitemaps include additional namespaces; we will search without prefix for loc.
    sitemap_urls = []
    for sitemap in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}sitemap'):
        loc = sitemap.find('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
        if loc is not None and loc.text:
            sitemap_urls.append(loc.text.strip())
    # Filter to news-related sitemaps (contain 'news' in filename) – safer but we process all.
    # Keep a dict of url -> date
    seen = {}
    for sm_url in sitemap_urls:
        sm_root = fetch_xml(sm_url)
        if sm_root is None:
            continue
        # Sitemap may use default namespace; discover it.
        nsmap = {k: v for k, v in sm_root.attrib.items() if k.startswith('xmlns')}
        # Find all <url> entries
        for url_el in sm_root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}url'):
            loc_el = url_el.find('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
            if loc_el is None or not loc_el.text:
                continue
            url = loc_el.text.strip()
            # Try news:publication_date if present
            pub_date = None
            news_el = url_el.find('{http://www.google.com/schemas/sitemap-news/0.9}news')
            if news_el is not None:
                pub_el = news_el.find('{http://www.google.com/schemas/sitemap-news/0.9}publication_date')
                if pub_el is not None and pub_el.text:
                    pub_date = iso_to_date(pub_el.text.strip())
            # Fallback: extract date from URL pattern /YYYY/MM/DD/
            if not pub_date:
                # look for /YYYY/MM/DD/ in the URL
                import re
                m = re.search(r"/(\d{4})/(\d{2})/(\d{2})/", url)
                if m:
                    pub_date = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
            if not pub_date:
                continue
            if TARGET_START <= pub_date <= TARGET_END:
                seen[url] = pub_date
        # optional progress print
        print(f"Processed sitemap {sm_url}: collected {len(seen)} URLs so far", file=sys.stderr)

    # Write output
    out_path = os.path.normpath(OUT)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    rows = sorted(seen.items(), key=lambda kv: (kv[1], kv[0]))
    with open(out_path, "w", encoding="utf-8") as f:
        for url, date in rows:
            f.write(f"{url}\t{date}\n")
    # Per‑day counts
    per_day = {}
    for _, d in rows:
        per_day[d] = per_day.get(d, 0) + 1
    print(f"wrote {len(rows)} unique URLs to {out_path}", file=sys.stderr)
    for day in sorted(per_day):
        print(f"{day}\t{per_day[day]}", file=sys.stderr)

if __name__ == "__main__":
    main()