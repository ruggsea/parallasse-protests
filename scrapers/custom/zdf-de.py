import sys, re, datetime, collections, xml.etree.ElementTree as ET

# Ensure polite_fetch is available
sys.path.insert(0, "scrapers")
from polite_fetch import fetch

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)
TARGET_DATES = [datetime.date(2026, 9, 30), datetime.date(2026, 10, 10), datetime.date(2026, 10, 20)]

MONTHS = {
    "januar": "01",
    "februar": "02",
    "maerz": "03",
    "märz": "03",
    "april": "04",
    "mai": "05",
    "juni": "06",
    "juli": "07",
    "august": "08",
    "september": "09",
    "oktober": "10",
    "november": "11",
    "dezember": "12",
}

def extract_date_from_url(url):
    # Look for pattern like 20-oktober-2026
    m = re.search(r"/(\d{1,2})-([a-zäöüß]+)-(\d{4})(?:/|$)", url, re.IGNORECASE)
    if not m:
        return None
    day, month_str, year = m.groups()
    month_str = month_str.lower()
    month = MONTHS.get(month_str)
    if not month:
        return None
    try:
        return datetime.date(int(year), int(month), int(day))
    except ValueError:
        return None

def fetch_xml(url):
    status, text, _ = fetch(url)
    if status != 200:
        return None
    return ET.fromstring(text)

def main():
    # Sitemap index
    index_url = "https://www.zdf.de/mediathek-sitemap.xml"
    root = fetch_xml(index_url)
    if root is None:
        print("Failed to fetch sitemap index")
        return
    # Collect sub-sitemap URLs
    sitemap_urls = []
    for sm in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}sitemap'):
        loc = sm.find('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
        if loc is not None and loc.text:
            sitemap_urls.append(loc.text.strip())
    # Data structures
    urls_by_date = collections.defaultdict(set)
    # Process each sub-sitemap until we have enough per target day
    for sm_url in sitemap_urls:
        sm_root = fetch_xml(sm_url)
        if sm_root is None:
            continue
        for url_elem in sm_root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}url'):
            loc_el = url_elem.find('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
            if loc_el is None or not loc_el.text:
                continue
            url = loc_el.text.strip()
            # Try date from URL first
            pub_date = extract_date_from_url