import xml.etree.ElementTree as ET
import datetime
import json
import os

# Import the polite fetch helper – adjust import path if needed
try:
    from polite_fetch import fetch
except ImportError:
    # fallback: use requests if polite_fetch not available
    import requests
    def fetch(url):
        return requests.get(url, timeout=30).text

START_DATE = datetime.date(2026, 9, 25)
END_DATE = datetime.date(2026, 10, 25)

SITEMAP_BASE = "https://www.sbs.com.au/news/sitemap-article-"  # expects YYYY-MM.xml

def parse_sitemap(url: str):
    """Fetch a sitemap XML and yield (url, lastmod) tuples"""
    txt = fetch(url)
    root = ET.fromstring(txt)
    ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    for url_el in root.findall('ns:url', ns):
        loc = url_el.find('ns:loc', ns).text.strip()
        lm_el = url_el.find('ns:lastmod', ns)
        lastmod = lm_el.text.strip() if lm_el is not None else None
        yield loc, lastmod

def in_range(date_str: str) -> bool:
    if not date_str:
        return False
    try:
        d = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return False
    return START_DATE <= d <= END_DATE

def main():
    collected = {}
    # Determine which monthly sitemaps may contain needed dates
    months = []
    cur = START_DATE.replace(day=1)
    while cur <= END_DATE:
        months.append(cur.strftime("%Y-%m"))
        # next month
        if cur.month == 12:
            cur = cur.replace(year=cur.year + 1, month=1)
        else:
            cur = cur.replace(month=cur.month + 1)
    for month in months:
        sitemap_url = f"{SITEMAP_BASE}{month}.xml"
        for loc, lastmod in parse_sitemap(sitemap_url):
            if in_range(lastmod):
                collected[loc] = lastmod
    # Write TSV
    tsv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/urls_custom/sbs-com-au.tsv"))
    os.makedirs(os.path.dirname(tsv_path), exist_ok=True)
    with open(tsv_path, "w", encoding="utf-8") as f:
        for url, lm in sorted(collected.items()):
            f.write(f"{url}\t{lm}\n")
    # Write notes JSON
    notes_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../grids/custom/out/sbs-com-au.json"))
    os.makedirs(os.path.dirname(notes_path), exist_ok=True)
    notes = {
        "script": os.path.relpath(__file__, start=os.getcwd()),
        "generated": datetime.datetime.utcnow().isoformat() + "Z",
        "url_count": len(collected),
        "date_range": {"start": START_DATE.isoformat(), "end": END_DATE.isoformat()},
    }
    with open(notes_path, "w", encoding="utf-8") as f:
        json.dump(notes, f, indent=2)

if __name__ == "__main__":
    main()
