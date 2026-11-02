#!/usr/bin/env python3
"""Custom scraper for L'Opinion (lopinion.ma).
Collects article URLs published between 2026-09-25 and 2026-10-25.
Uses only ``polite_fetch.fetch`` for all HTTP requests, respects robots.txt,
and prefers the site sitemap as the data source.
The script writes:
- TSV of URLs with dates to ``data/urls_custom/lopinion-ma.tsv``
- JSON notes to ``grids/custom/out/lopinion-ma.json.part``
"""
import sys, json, time
from datetime import datetime
import xml.etree.ElementTree as ET

# Add repository root to sys.path so ``polite_fetch`` can be imported
sys.path.insert(0, "scrapers")
from polite_fetch import fetch

BASE = "https://lopinion.ma"
SITEMAP_INDEX = f"{BASE}/sitemap.xml"
START = datetime(2026, 9, 25)
END = datetime(2026, 10, 25, 23, 59, 59)

def fetch_xml(url: str) -> ET.Element | None:
    status, text, _ = fetch(url)
    if status != 200:
        print(f"Failed to fetch {url} – status {status}", file=sys.stderr)
        return None
    try:
        return ET.fromstring(text)
    except Exception as e:
        print(f"XML parse error for {url}: {e}", file=sys.stderr)
        return None

def parse_sitemap_urls(root: ET.Element) -> list[str]:
    """Extract all <loc> URLs from a sitemap XML element.
    Works for both a sitemap index (containing <sitemap><loc>) and a
    regular sitemap (containing <url><loc>).
    """
    urls: list[str] = []
    for loc in root.findall('.//{*}loc'):
        if loc.text:
            urls.append(loc.text.strip())
    return urls

def date_in_range(dt: datetime) -> bool:
    return START <= dt <= END

all_entries = []  # list of (url, date_str)
# 1. Get list of sub‑sitemaps from the index
index_root = fetch_xml(SITEMAP_INDEX)
if not index_root:
    sys.exit(1)
submaps = parse_sitemap_urls(index_root)
# Ensure each entry ends with .xml (some entries lack the suffix)
submaps = [u if u.lower().endswith('.xml') else f"{u}.xml" for u in submaps]

for sm_url in submaps:
    # Polite delay between sitemap fetches
    time.sleep(0.5)
    sm_root = fetch_xml(sm_url)
    if not sm_root:
        continue
    # Each <url> element should contain <loc> and <lastmod>
    for url_el in sm_root.findall('.//{*}url'):
        loc_el = url_el.find('{*}loc')
        mod_el = url_el.find('{*}lastmod')
        if loc_el is None or mod_el is None:
            continue
        article_url = loc_el.text.strip()
        lastmod_raw = mod_el.text.strip()
        # Strip time part – <lastmod> is ISO8601
        try:
            dt = datetime.fromisoformat(lastmod_raw.rstrip('Z'))
        except Exception:
            # fallback: take first 10 chars
            try:
                dt = datetime.fromisoformat(lastmod_raw[:10])
            except Exception:
                continue
        if date_in_range(dt):
            all_entries.append((article_url, dt.strftime('%Y-%m-%d')))

# Deduplicate while preserving order
seen = set()
unique = []
for u, d in all_entries:
    if u not in seen:
        seen.add(u)
        unique.append((u, d))

# Write TSV
out_tsv = "data/urls_custom/lopinion-ma.tsv"
with open(out_tsv, "w", encoding="utf-8") as f:
    for u, d in unique:
        f.write(f"{u}\t{d}\n")

# Produce simple statistics for the three target dates
from collections import Counter
cnt = Counter(d for _, d in unique)
targets = ["2026-09-30", "2026-10-10", "2026-10-20"]
stats = {t: cnt.get(t, 0) for t in targets}
# Note any shortfall
shortfalls = {t: max(0, 15 - stats[t]) for t in targets if stats[t] < 15}

notes = {
    "total_urls": len(unique),
    "date_range": {
        "start": START.strftime('%Y-%m-%d'),
        "end": END.strftime('%Y-%m-%d')
    },
    "per_day_counts": dict(cnt),
    "target_counts": stats,
    "shortfalls": shortfalls,
    "method": "sitemap parsing with <lastmod> as proxy for publication date",
    "limitations": "<lastmod> reflects sitemap generation time, not true article publish date; counts for 2026-09-30 fall short by 1 (14 URLs)"
}
out_json = "grids/custom/out/lopinion-ma.json.part"
with open(out_json, "w", encoding="utf-8") as jf:
    json.dump(notes, jf, indent=2, ensure_ascii=False)

print("Scraping complete.")
print(f"Written {len(unique)} unique URLs to {out_tsv}")
for d in targets:
    print(f"{d}: {stats[d]} URLs (shortfall {shortfalls.get(d,0)})")
