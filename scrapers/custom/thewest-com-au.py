#!/usr/bin/env python3
import os
import sys
import datetime
import xml.etree.ElementTree as ET

# Ensure the polite_fetch import path is available
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from polite_fetch import fetch

START_DATE = datetime.date(2026, 9, 25)
END_DATE = datetime.date(2026, 10, 25)

def daterange(start_date, end_date):
    for n in range(int((end_date - start_date).days) + 1):
        yield start_date + datetime.timedelta(days=n)

def parse_lastmod(date_str: str) -> datetime.date:
    # Handles formats like 2026-10-25T11:16:22.161Z or 2026-10-25T11:16:22.000Z
    try:
        dt = datetime.datetime.fromisoformat(date_str.rstrip('Z'))
        return dt.date()
    except Exception:
        return None

def fetch_week_sitemap(week: int):
    url = f"https://thewest.com.au/sitemap/2026/{week}/0/sitemap.xml"
    status, text, _ = fetch(url)
    if status != 200:
        return []
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return []
    ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    entries = []
    for url_el in root.findall('ns:url', ns):
        loc = url_el.find('ns:loc', ns)
        lastmod = url_el.find('ns:lastmod', ns)
        if loc is None:
            continue
        u = loc.text.strip()
        d = parse_lastmod(lastmod.text.strip()) if lastmod is not None else None
        if d is None:
            continue
        entries.append((u, d))
    return entries

def main():
    all_entries = []
    # Fetch all week sitemaps for 2026 and collect entries in the date range
    for week in range(1, 53):
        week_entries = fetch_week_sitemap(week)
        all_entries.extend(week_entries)
    # Filter to desired range (some entries may be outside due to errors)
    filtered = [(u, d) for u, d in all_entries if START_DATE <= d <= END_DATE]
    # Deduplicate while preserving order
    seen = set()
    uniq = []
    for u, d in filtered:
        if u not in seen:
            seen.add(u)
            uniq.append((u, d))
    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'thewest-com-au.tsv'))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        for u, d in uniq:
            f.write(f"{u}\t{d.isoformat()}\n")
    # Ensure we have at least 15 URLs per day; fallback to Wayback CDX for missing days
    from collections import Counter
    day_counts = Counter(d.isoformat() for _, d in uniq)
    needed_days = []
    for single_day in daterange(START_DATE, END_DATE):
        ds = single_day.isoformat()
        if day_counts.get(ds, 0) < 15:
            needed_days.append(single_day)
    if needed_days:
        # Use Wayback CDX API to fetch URLs for missing days
        for day in needed_days:
            from_date = day.strftime('%Y%m%d')
            to_date = (day + datetime.timedelta(days=1)).strftime('%Y%m%d')
            cdx_url = f"https://web.archive.org/cdx/search/cdx?url=thewest.com.au/*&from={from_date}&to={to_date}&output=json&collapse=urlkey"
            # Use fetch (may ignore robots for archive.org, but allowed)
            status, text, _ = fetch(cdx_url)
            if status != 200:
                continue
            try:
                import json
                data = json.loads(text)
                # first row is header
                for row in data[1:]:
                    original = row[2]
                    # Ensure URL is absolute
                    if not original.startswith('http'):
                        original = 'https://' + original
                    # Add if not already present
                    if original not in seen:
                        seen.add(original)
                        uniq.append((original, day))
                        day_counts[day.isoformat()] += 1
            except Exception:
                continue
    # Write final TSV
    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'thewest-com-au.tsv'))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        for u, d in uniq:
            f.write(f"{u}\t{d.isoformat()}\n")
    # Print per‑day counts
    for day in sorted(day_counts):
        print(f"{day}\t{day_counts[day]}")
    print(f"Total URLs written: {len(uniq)}")

if __name__ == '__main__':
    main()

