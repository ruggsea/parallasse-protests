#!/usr/bin/env python3
"""Scrape article URLs from RTVC (Colombia) for 2026-09-25 to 2026-10-25.
Writes a TSV with URL and publication date (YYYY-MM-DD) to
`data/urls_custom/rtvc-gov-co.tsv`.
Uses the site's sitemap (https://www.rtvc.gov.co/sitemap.xml?page=N) via
`polite_fetch.fetch` which respects robots.txt and rate limits.
"""
import sys, os, csv, datetime, xml.etree.ElementTree as ET

# Add the scraper directory to sys.path for polite_fetch import
scraper_dir = os.path.abspath(os.path.join(__file__, os.pardir, os.pardir))
if scraper_dir not in sys.path:
    sys.path.insert(0, scraper_dir)

try:
    from polite_fetch import fetch
except ImportError:
    sys.stderr.write("polite_fetch module not found. Ensure it is in the scraper path.\n")
    sys.exit(1)

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)
BASE_SITEMAP = "https://www.rtvc.gov.co/sitemap.xml?page={}"  # paginated sitemap

collected = {}  # date -> set of URLs

page = 1
while True:
    url = BASE_SITEMAP.format(page)
    status, text, _ = fetch(url)
    if status != 200:
        # non‑200 – assume no more pages
        break
    # Detect if we got HTML instead of XML (some pages return a site page)
    if text.lstrip().startswith("<!DOCTYPE html"):
        break
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        break
    # Namespace handling
    ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    for url_el in root.findall('ns:url', ns):
        loc = url_el.find('ns:loc', ns)
        if loc is None or not loc.text:
            continue
        link = loc.text.strip()
        # Only consider article pages – they contain '/noticia/' in the path
        if '/noticia/' not in link:
            continue
        date_str = None
        lastmod = url_el.find('ns:lastmod', ns)
        if lastmod is not None and lastmod.text:
            # Example format: 2026-10-22T15:54Z
            date_part = lastmod.text.strip().split('T')[0]
            date_str = date_part
        else:
            # Fallback: try to extract YYYY/MM/DD from URL if present
            # e.g. https://www.rtvc.gov.co/noticia/2026/10/20/... (not observed but safety)
            parts = link.split('/')
            for i in range(len(parts) - 2):
                if parts[i].isdigit() and len(parts[i]) == 4:
                    yr = int(parts[i])
                    mo = int(parts[i+1]) if parts[i+1].isdigit() else None
                    da = int(parts[i+2]) if parts[i+2].isdigit() else None
                    if mo and da:
                        date_str = f"{yr:04d}-{mo:02d}-{da:02d}"
                        break
        if not date_str:
            continue
        try:
            d = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            continue
        if START <= d <= END:
            collected.setdefault(d, set()).add(link)
    page += 1

# If sitemap yielded too few URLs, fall back to Wayback CDX
need_more = any(len(collected.get(d, [])) < 15 for d in [datetime.date(2026,9,30), datetime.date(2026,10,10), datetime.date(2026,10,20)])
if need_more:
    cdx_url = f"https://web.archive.org/cdx/search/cdx?url=rtvc.gov.co/*&from=20260925&to=20261025&output=json&collapse=urlkey"
    status, text, _ = fetch(cdx_url)
    if status == 200:
        import json
        try:
            rows = json.loads(text)
        except json.JSONDecodeError:
            rows = []
        for row in rows[1:]:  # skip header
            if len(row) < 3:
                continue
            original = row[2]
            if '/noticia/' not in original:
                continue
            ts = row[1]
            try:
                d = datetime.datetime.strptime(ts[:8], "%Y%m%d").date()
            except ValueError:
                continue
            if START <= d <= END:
                collected.setdefault(d, set()).add(original)

# Write TSV
output_path = os.path.abspath(os.path.join(__file__, os.pardir, os.pardir, "..", "data", "urls_custom", "rtvc-gov-co.tsv"))
os.makedirs(os.path.dirname(output_path), exist_ok=True)
with open(output_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f, delimiter="\t")
    # Sort by date then URL for reproducibility
    for d in sorted(collected):
        for link in sorted(collected[d]):
            writer.writerow([link, d.isoformat()])

# Print per‑day counts
for d in sorted(collected):
    print(f"{d.isoformat()}: {len(collected[d])} URLs")

print(f"Wrote {sum(len(s) for s in collected.values())} URLs to {output_path}")
