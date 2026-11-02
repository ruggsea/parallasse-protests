import re, sys, os, datetime

# Ensure polite_fetch is on sys.path

# We will paginate through the news listing using the 'start' query parameter.
# The site returns up to around 100 items per page. We stop when a page yields no new URLs.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from polite_fetch import fetch

BASE = "https://tv5.mn"
NEWS_URL = f"{BASE}/index.php/news"
START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

def fetch_page(start):
    # The site expects a 'start' query parameter for pagination, even for the first page.
    url = f"{NEWS_URL}?start={start}"
    s, h, _ = fetch(url)
    return s, h

status, html = fetch_page(0)
if status != 200:
    sys.stderr.write(f"Failed to fetch {NEWS_URL}: status {status}\n")
    sys.exit(1)

records = []
seen_urls = set()
start = 0
while True:
    # Parse current page
    pattern = re.compile(r'<a href="(?P<href>/index\.php/[^\"]+)"[^>]*>.*?<time datetime="(?P<dt>[^\"]+)"', re.S)
    page_records = []
    for m in pattern.finditer(html):
        href = m.group('href')
        dt_str = m.group('dt')
        date_part = dt_str.split('T')[0]
        try:
            d = datetime.datetime.strptime(date_part, "%Y-%m-%d").date()
        except ValueError:
            continue
        if START <= d <= END:
            full_url = BASE + href
            if full_url not in seen_urls:
                seen_urls.add(full_url)
                page_records.append((full_url, d.isoformat()))
    if not page_records:
        break
    records.extend(page_records)
    # fetch next page
    start += 100
    status, html = fetch_page(start)
    if status != 200:
        break
    # Stop if next page fetch fails

# records already collected in pagination loop

# Deduplicate URLs while preserving order
seen = set()
unique = []
for url, d in records:
    if url not in seen:
        seen.add(url)
        unique.append((url, d))

out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'tv5-mn.tsv'))
os.makedirs(os.path.dirname(out_path), exist_ok=True)
with open(out_path, 'w', encoding='utf-8') as f:
    for url, d in unique:
        f.write(f"{url}\t{d}\n")

# Report per‑day counts
from collections import Counter
counter = Counter(d for _, d in unique)
for day in sorted(counter):
    print(f"{day}\t{counter[day]}")

print(f"Wrote {len(unique)} URLs to {out_path}")
