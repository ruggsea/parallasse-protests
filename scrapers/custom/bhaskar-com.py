import sys, os, csv, json
import datetime
import xml.etree.ElementTree as ET

# Ensure polite_fetch is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from polite_fetch import fetch

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

SITEMAP_INDEX = "https://www.bhaskar.com/sitemaps-v1--sitemap-google-news-index.xml"


def iso_to_date(s: str) -> datetime.date | None:
    """Convert ISO‑8601 or simple YYYY‑MM‑DD strings to a date."""
    try:
        return datetime.datetime.fromisoformat(s.replace('Z', '+00:00')).date()
    except Exception:
        try:
            return datetime.datetime.strptime(s, "%Y-%m-%d").date()
        except Exception:
            return None


def fetch_url(url: str) -> str | None:
    status, text, _ = fetch(url)
    if status != 200:
        print(f"Failed {status} fetching {url}", file=sys.stderr)
        return None
    return text


def parse_sitemap(url: str):
    txt = fetch_url(url)
    if txt is None:
        return []
    root = ET.fromstring(txt)
    ns = {
        'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9',
        'news': 'http://www.google.com/schemas/sitemap-news/0.9',
    }
    entries = []
    for url_el in root.findall('ns:url', ns):
        loc = url_el.find('ns:loc', ns)
        if loc is None or not loc.text:
            continue
        url_text = loc.text.strip()
        # Prefer news:publication_date, fall back to lastmod
        pub_el = url_el.find('.//news:publication_date', ns)
        date_str = pub_el.text.strip() if pub_el is not None and pub_el.text else None
        if not date_str:
            lastmod = url_el.find('ns:lastmod', ns)
            if lastmod is not None and lastmod.text:
                date_str = lastmod.text.strip()
        if not date_str:
            continue
        d = iso_to_date(date_str)
        if d is None:
            continue
        if START <= d <= END:
            entries.append((url_text, d.isoformat()))
    return entries


def fallback_wayback(entries, seen):
    """Fetch Wayback CDX for any missing dates and add to entries."""
    covered = {datetime.datetime.strptime(date, "%Y-%m-%d").date() for _, date in entries}
    needed = {START + datetime.timedelta(days=i) for i in range((END - START).days + 1)} - covered
    if not needed:
        return
    # Use HTTPS for Wayback CDX
    cdx_url = (
        f"https://web.archive.org/cdx/search/cdx?url=www.bhaskar.com/*"
        f"&from={START.isoformat()}&to={END.isoformat()}&output=json&collapse=urlkey"
    )
    txt = fetch_url(cdx_url)
    if not txt:
        return
    try:
        rows = json.loads(txt)
    except Exception:
        return
    for row in rows[1:]:  # skip header
        url, timestamp = row[0], row[1]
        try:
            dt = datetime.datetime.strptime(timestamp, "%Y%m%d%H%M%S")
        except Exception:
            continue
        d = dt.date()
        if START <= d <= END and url not in seen:
            seen.add(url)
            entries.append((url, d.isoformat()))


def write_output(entries):
    # Sort for reproducibility
    entries.sort(key=lambda x: (x[1], x[0]))
    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'bhaskar-com.tsv'))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        writer = csv.writer(f, delimiter='\t')
        for url, date in entries:
            writer.writerow([url, date])
    # Print per‑day counts (useful for manual checks)
    counts = {}
    for _, d in entries:
        counts[d] = counts.get(d, 0) + 1
    for d in sorted(counts):
        print(f"{d}\t{counts[d]}")


def main():
    # 1. Process Google‑News sitemaps
    index_txt = fetch_url(SITEMAP_INDEX)
    if index_txt is None:
        sys.exit(1)
    index_root = ET.fromstring(index_txt)
    ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    sitemap_urls = [el.find('ns:loc', ns).text.strip()
                    for el in index_root.findall('ns:sitemap', ns)
                    if el.find('ns:loc', ns) is not None]
    entries = []
    seen = set()
    for sm_url in sitemap_urls:
        for url, date in parse_sitemap(sm_url):
            if url not in seen:
                seen.add(url)
                entries.append((url, date))
    # 2. Fallback to Wayback if any day missing
    fallback_wayback(entries, seen)
    # 3. Write TSV
    write_output(entries)

if __name__ == "__main__":
    main()
