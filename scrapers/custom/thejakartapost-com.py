import sys, os, datetime, csv, collections

# Ensure the project’s scraper utilities are on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from polite_fetch import fetch

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

SITEMAP_INDEX_URL = "https://www.thejakartapost.com/sitemap_index.xml"

def parse_iso_date(date_str: str) -> datetime.date:
    """Parse ISO date (with or without time) into a date object."""
    # Strip timezone if present
    if '+' in date_str:
        date_str = date_str.split('+')[0]
    try:
        return datetime.datetime.fromisoformat(date_str).date()
    except ValueError:
        # Fallback for plain YYYY-MM-DD
        return datetime.datetime.strptime(date_str, "%Y-%m-%d").date()

def main():
    # Fetch sitemap index
    status, index_text, _ = fetch(SITEMAP_INDEX_URL)
    if status != 200:
        print(f"Failed to fetch sitemap index ({status})")
        return
    try:
        import xml.etree.ElementTree as ET
        index_root = ET.fromstring(index_text)
    except ET.ParseError as e:
        print(f"Index XML parse error: {e}")
        return

    ns = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
    sitemap_urls = []
    for sm in index_root.findall(f".//{ns}sitemap"):
        loc = sm.find(f"{ns}loc")
        if loc is not None and loc.text:
            sitemap_urls.append(loc.text.strip())

    urls: dict[str, str] = {}
    ns_sitemap = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
    ns_news = "{http://www.google.com/schemas/sitemap-news/0.9}"

    for sm_url in sitemap_urls:
        sm_status, sm_text, _ = fetch(sm_url)
        if sm_status != 200:
            continue
        try:
            sm_root = ET.fromstring(sm_text)
        except ET.ParseError:
            continue
        # Determine type by presence of news namespace
        is_news = any('news' in tag for tag in sm_text.split())
        for url_el in sm_root.findall(f".//{ns_sitemap}url"):
            loc_el = url_el.find(f"{ns_sitemap}loc")
            if loc_el is None or not loc_el.text:
                continue
            url = loc_el.text.strip()
            if is_news:
                pub_el = url_el.find(f".//{ns_news}publication_date")
                if pub_el is None or not pub_el.text:
                    continue
                pub_date = parse_iso_date(pub_el.text.strip())
            else:
                mod_el = url_el.find(f"{ns_sitemap}lastmod")
                if mod_el is None or not mod_el.text:
                    continue
                pub_date = parse_iso_date(mod_el.text.strip())
            if START <= pub_date <= END:
                urls[url] = pub_date.isoformat()

    # Write TSV
    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "urls_custom", "thejakartapost-com.tsv"))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter="\t")
        for url, date in sorted(urls.items(), key=lambda x: (x[1], x[0])):
            writer.writerow([url, date])

    # Print per‑day counts
    counts = collections.Counter(urls.values())
    for d in sorted(counts):
        print(f"{d}\t{counts[d]}")

if __name__ == "__main__":
    main()
