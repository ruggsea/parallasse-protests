import sys, os, csv, datetime, xml.etree.ElementTree as ET

# Ensure polite_fetch is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from polite_fetch import fetch

BASE_URL = 'https://www.elnuevosiglo.com.co/sitemap.xml'
START_DATE = datetime.date(2026, 9, 25)
END_DATE = datetime.date(2026, 10, 25)

output_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'elnuevosiglo-com-co.tsv'))
os.makedirs(os.path.dirname(output_path), exist_ok=True)

seen = set()
url_to_date = {}
counts_per_day = {}

page = 1
while True:
    sitemap_url = f"{BASE_URL}?page={page}"
    status, text, _ = fetch(sitemap_url)
    if status != 200:
        print(f"Failed to fetch {sitemap_url}: status {status}", file=sys.stderr)
        break
    # Parse XML
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        print(f"XML parse error on page {page}: {e}", file=sys.stderr)
        break
    ns = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    urls = root.findall('.//sm:url', ns)
    if not urls:
        # No more URLs
        break
    added_any = False
    for u in urls:
        loc_el = u.find('sm:loc', ns)
        lastmod_el = u.find('sm:lastmod', ns)
        if loc_el is None or lastmod_el is None:
            continue
        url = loc_el.text.strip()
        # Parse date part
        try:
            dt = datetime.datetime.fromisoformat(lastmod_el.text.strip())
        except ValueError:
            # fallback to date only
            try:
                dt = datetime.datetime.strptime(lastmod_el.text.strip(), '%Y-%m-%d')
            except Exception:
                continue
        date = dt.date()
        if START_DATE <= date <= END_DATE and url not in seen:
            seen.add(url)
            url_to_date[url] = date.isoformat()
            added_any = True
            day_str = date.isoformat()
            counts_per_day[day_str] = counts_per_day.get(day_str, 0) + 1
    if not added_any:
        # Still may have more pages but none in range, continue to fetch next page until empty
        pass
    print(f"Processed page {page}, collected {len(seen)} URLs so far")
    page += 1
    # Safety stop if too many pages
    if page > 1000:
        print("Too many pages, stopping", file=sys.stderr)
        break

# Write TSV
with open(output_path, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f, delimiter='\t')
    for url, date in sorted(url_to_date.items()):
        writer.writerow([url, date])

# Print per‑day counts
print('URLs written per day:')
for day in sorted(counts_per_day):
    print(f"{day}\t{counts_per_day[day]}")

# The above stub will be refined later.
