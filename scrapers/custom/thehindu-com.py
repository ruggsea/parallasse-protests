#!/usr/bin/env python3
"""Scrape article URLs from The Hindu (thehindu.com) for the window
2026-09-25 to 2026-10-25.
Uses the Google News sitemap which provides <news:publication_date>.
Writes a TSV with "URL<TAB>YYYY-MM-DD" to data/urls_custom/thehindu-com.tsv.
"""
import sys, os, datetime, xml.etree.ElementTree as ET

# Ensure polite_fetch is importable
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scrapers"))
try:
    from polite_fetch import fetch
except ImportError:
    sys.stderr.write("polite_fetch not found, abort\n")
    sys.exit(1)

SITEMAP_URL = "https://www.thehindu.com/sitemap/googlenews/all/all.xml"
START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

def iso_to_date(s):
    # s like 2026-10-26T12:09:45+05:30
    # Strip timezone offset for fromisoformat compatibility
    if s is None:
        return None
    # split at +/-
    if '+' in s:
        s = s.split('+')[0]
    elif '-' in s[10:]:  # timezone negative after date
        # last '-' before timezone
        parts = s.rsplit('-', 1)
        s = parts[0]
    try:
        dt = datetime.datetime.fromisoformat(s)
        return dt.date()
    except Exception:
        return None

def main():
    status, text, _ = fetch(SITEMAP_URL)
    if status != 200:
        sys.stderr.write(f"Failed to fetch sitemap, status {status}\n")
        sys.exit(1)
    # Parse XML with namespaces
    # Also fetch Wayback CDX as fallback for older dates
    ns = {
        "ns": "http://www.sitemaps.org/schemas/sitemap/0.9",
        "news": "http://www.google.com/schemas/sitemap-news/0.9",
    }
    root = ET.fromstring(text)
    # -------------------
    # Wayback CDX fallback
    WAYBACK_URL = f"https://web.archive.org/cdx/search/cdx?url=www.thehindu.com/*&from=20260925&to=20261025&output=json&collapse=urlkey"
    w_status, w_text, _ = fetch(WAYBACK_URL)
    wayback_entries = []
    if w_status == 200:
        try:
            import json
            data = json.loads(w_text)
            # first row is header
            for row in data[1:]:
                # row format: [urlkey, timestamp, original, mime, status, digest, length]
                timestamp = row[1]
                url = row[2]
                # timestamp like YYYYMMDDhhmmss
                try:
                    dt = datetime.datetime.strptime(timestamp, "%Y%m%d%H%M%S")
                    d = dt.date()
                except Exception:
                    continue
                if START <= d <= END:
                    wayback_entries.append((url, d.isoformat()))
        except Exception as e:
            sys.stderr.write(f"Wayback parse error: {e}\n")
    else:
        sys.stderr.write(f"Wayback fetch failed status {w_status}\n")

    rows = []
    # collect from sitemap first
    for url_el in root.findall('ns:url', ns):
        loc_el = url_el.find('ns:loc', ns)
        if loc_el is None:
            continue
        url = loc_el.text.strip()
        # Try news:publication_date
        pub_date = None
        news_el = url_el.find('news:news', ns)
        if news_el is not None:
            pub_el = news_el.find('news:publication_date', ns)
            if pub_el is not None:
                pub_date = iso_to_date(pub_el.text.strip())
        # Fallback to lastmod
        if pub_date is None:
            lastmod_el = url_el.find('ns:lastmod', ns)
            if lastmod_el is not None:
                pub_date = iso_to_date(lastmod_el.text.strip())
        if pub_date is None:
            continue
        if START <= pub_date <= END:
            rows.append((url, pub_date.isoformat()))
    # Add Wayback entries
    rows.extend(wayback_entries)
    # Deduplicate
    seen = set()
    uniq = []
    for u, d in rows:
        if u not in seen:
            seen.add(u)
            uniq.append((u, d))
    # Ensure output directory exists
    out_path = os.path.join("data", "urls_custom", "thehindu-com.tsv")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for u, d in uniq:
            f.write(f"{u}\t{d}\n")
    # Summary per day
    from collections import Counter
    cnt = Counter(d for _, d in uniq)
    for day in sorted(cnt.keys()):
        print(f"{day}\t{cnt[day]}")
    print(f"Total URLs written: {len(uniq)}")

if __name__ == "__main__":
    main()
