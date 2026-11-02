import sys, os, json, datetime, time, xml.etree.ElementTree as ET

# Ensure polite_fetch is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
# The project adds a helper path in other scrapers; here we add the root scrapers directory
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scrapers"))
from polite_fetch import fetch

def fetch_day_sitemap(day: datetime.date):
    """Fetch the per‑day news sitemap for *day*.
    Returns a list of (url, pub_date) tuples where pub_date is YYYY‑MM‑DD.
    """
    day_str = day.strftime("%Y-%m-%d")
    sitemap_url = f"https://www.eluniverso.com/sitemaps/{day_str}/noticias.xml/"
    status, text, _ = fetch(sitemap_url)
    if status != 200:
        # Some days may not have a sitemap yet – treat as empty.
        print(f"No sitemap for {day_str} (status {status})")
        return []
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        print(f"XML parse error for {day_str}: {e}")
        return []
    ns = {
        'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9',
        'news': 'http://www.google.com/schemas/sitemap-news/0.9',
    }
    results = []
    for url_el in root.findall('ns:url', ns):
        loc_el = url_el.find('ns:loc', ns)
        news_date_el = url_el.find('news:news/news:publication_date', ns)
        if loc_el is None or news_date_el is None:
            continue
        url = loc_el.text.strip()
        pub_ts = news_date_el.text.strip()
        # Take the date part before the T
        pub_date = pub_ts.split('T')[0]
        results.append((url, pub_date))
    return results


def main():
    # Output TSV path
    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'eluniverso-com.tsv'))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    start = datetime.date(2026, 9, 25)
    end = datetime.date(2026, 10, 25)
    seen = set()
    per_day = {}
    with open(out_path, 'w', encoding='utf-8') as f:
        cur = start
        while cur <= end:
            entries = fetch_day_sitemap(cur)
            for url, pub_date in entries:
                if url in seen:
                    continue
                seen.add(url)
                f.write(f"{url}\t{pub_date}\n")
                per_day[pub_date] = per_day.get(pub_date, 0) + 1
            # Be gentle; crawl‑delay from robots.txt is 10 s, but polite_fetch respects it.
            time.sleep(1)
            cur += datetime.timedelta(days=1)
    for d in sorted(per_day):
        print(f"{d}: {per_day[d]} URLs")

if __name__ == '__main__':
    main()
