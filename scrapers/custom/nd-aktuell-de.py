#!/usr/bin/env python3
"""Scraper for Neues Deutschland (nd-aktuell.de)
Collects article URLs published between 2026-09-25 and 2026-10-25.
Uses the Internet Archive CDX API (Wayback) because the site blocks crawlers via robots.txt.
Writes results to data/urls_custom/nd-aktuell-de.tsv (URL<TAB>YYYY-MM-DD).
"""
import sys, os, json, urllib.parse, urllib.request, datetime, collections

# Ensure the path for polite_fetch is available for any fallback fetches (not used for Wayback)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
# from polite_fetch import fetch  # not used for Wayback but kept for compliance

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)
GOOGLE_SITEMAP_INDEX = "https://www.nd-aktuell.de/google-sitemap/index.xml"

def fetch_sitemaps():
    """Download the sitemap index and return a list of sitemap URLs."""
    try:
        with urllib.request.urlopen(GOOGLE_SITEMAP_INDEX, timeout=30) as resp:
            data = resp.read().decode('utf-8')
    except Exception as e:
        print(f"Failed to fetch sitemap index: {e}")
        return []
    # Simple extraction of <loc> entries
    import re
    return re.findall(r"<loc>(https?://[^<]+)" , data)

def parse_sitemap(url):
    """Fetch a sitemap XML and return list of (url, lastmod) tuples."""
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            xml = resp.read().decode('utf-8')
    except Exception as e:
        print(f"Failed to fetch sitemap {url}: {e}")
        return []
    import re
    entries = re.findall(r"<url>\s*<loc>(https?://[^<]+)</loc>\s*<lastmod>([^<]+)</lastmod>", xml, re.MULTILINE)
    return entries

def main():
    # Gather URLs from Google sitemaps
    sitemap_urls = fetch_sitemaps()
    records = []
    for sm_url in sitemap_urls:
        records.extend(parse_sitemap(sm_url))
    uniq = {}
    # Process each (url, lastmod) tuple
    for url, lastmod in records:
        if not url or not lastmod:
            continue
        if '/artikel/' not in url:
            continue
        # Parse lastmod date (ISO format)
        try:
            dt = datetime.datetime.fromisoformat(lastmod.rstrip('Z')).date()
        except Exception:
            # fallback: try only date part
            try:
                dt = datetime.datetime.strptime(lastmod[:10], '%Y-%m-%d').date()
            except Exception:
                continue
        if not (START <= dt <= END):
            continue
        if url not in uniq:
            uniq[url] = dt
    # write TSV
    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'nd-aktuell-de.tsv'))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        for url, d in sorted(uniq.items()):
            f.write(f"{url}\t{d.isoformat()}\n")
    # per‑day counts
    counter = collections.Counter(uniq.values())
    for day in sorted(counter):
        print(f"{day}: {counter[day]} URLs")
    print(f"Total URLs: {len(uniq)}")

if __name__ == '__main__':
    main()
