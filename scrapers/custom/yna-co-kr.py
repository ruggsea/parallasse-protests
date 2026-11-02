import sys, os, datetime, xml.etree.ElementTree as ET

# Ensure import path for polite_fetch
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from polite_fetch import fetch
except ImportError:
    sys.exit('polite_fetch not found')

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

SITEMAPS = [
    "https://www.yna.co.kr/news-sitemap3.xml",
    "https://www.yna.co.kr/news-sitemap4.xml",
    "https://www.yna.co.kr/news-sitemap5.xml",
    "https://www.yna.co.kr/news-sitemap6.xml",
]

out_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom'))
os.makedirs(out_dir, exist_ok=True)
out_path = os.path.join(out_dir, 'yna-co-kr.tsv')

urls_by_date = {}

for sm in SITEMAPS:
    status, text, _ = fetch(sm)
    if status != 200:
        print(f"Failed to fetch sitemap {sm}: status {status}", file=sys.stderr)
        continue
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        print(f"XML parse error for {sm}: {e}", file=sys.stderr)
        continue
    # namespace handling
    ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9',
          'news': 'http://www.google.com/schemas/sitemap-news/0.9'}
    for url_el in root.findall('ns:url', ns):
        loc = url_el.find('ns:loc', ns)
        news_pub = url_el.find('news:news/news:publication_date', ns)
        if loc is None or news_pub is None:
            continue
        url = loc.text.strip()
        pub_str = news_pub.text.strip()
        # parse date part
        try:
            pub_dt = datetime.datetime.fromisoformat(pub_str.rstrip('Z'))
        except ValueError:
            continue
        pub_date = pub_dt.date()
        if START <= pub_date <= END:
            urls_by_date.setdefault(pub_date, set()).add(url)

# Write TSV sorted by date then url
with open(out_path, 'w', encoding='utf-8') as f:
    for d in sorted(urls_by_date):
        for u in sorted(urls_by_date[d]):
            f.write(f"{u}\t{d.isoformat()}\n")

# Fallback: Wayback CDX API
cdx_url = (
    "https://web.archive.org/cdx/search/cdx?url=www.yna.co.kr/*"
    "&from=20260925&to=20261025&output=json&limit=10000"
)
status, text, _ = fetch(cdx_url)
if status == 200:
    import json as _json
    lines = _json.loads(text)
    # first line is field names
    for entry in lines[1:]:
        original = entry[2]
        if '/view/AKR' not in original:
            continue
        ts = entry[1]  # YYYYMMDDhhmmss
        try:
            pub_date = datetime.datetime.strptime(ts[:8], "%Y%m%d").date()
        except ValueError:
            continue
        if START <= pub_date <= END:
            urls_by_date.setdefault(pub_date, set()).add(original)

# Print per‑day counts
for d in sorted(urls_by_date):
    print(f"{d.isoformat()}: {len(urls_by_date[d])} URLs")
