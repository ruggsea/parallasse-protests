import sys, os, re, json, datetime, collections, time

# Ensure polite_fetch is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from polite_fetch import fetch
except ImportError:
    print('polite_fetch not found')
    sys.exit(1)

START_DATE = datetime.date(2026, 9, 25)
END_DATE = datetime.date(2026, 10, 25)
TARGET_DATES = [datetime.date(2026, 9, 30), datetime.date(2026, 10, 10), datetime.date(2026, 10, 20)]
MIN_PER_DAY = 15

ARABIC_MONTHS = {
    'كانون الثاني': 1, 'شباط': 2, 'آذار': 3, 'نيسان': 4, 'أيار': 5, 'حزيران': 6,
    'تموز': 7, 'آب': 8, 'أيلول': 9, 'تشرين الأول': 10, 'تشرين الثاني': 11, 'كانون الأول': 12,
    # common Arabic names
    'يناير':1,'فبراير':2,'مارس':3,'أبريل':4,'مايو':5,'يونيو':6,'يوليو':7,'أغسطس':8,'سبتمبر':9,'أكتوبر':10,'نوفمبر':11,'ديسمبر':12,
}

def parse_arabic_date(text):
    # Expected format: DD Month YYYY (Arabic month name possibly with spaces)
    m = re.search(r"([0-9]{1,2})\s+([^\s]+(?:\s+[^\s]+)?)\s+(\d{4})", text)
    if not m:
        return None
    day = int(m.group(1))
    month_name = m.group(2).strip()
    year = int(m.group(3))
    month = ARABIC_MONTHS.get(month_name)
    if not month:
        return None
    try:
        return datetime.date(year, month, day)
    except ValueError:
        return None

def fetch_article_date(url):
    status, text, _ = fetch(url)
    if status != 200:
        return None
    # Find the date div
    m = re.search(r"تاريخ النشر:\s*([^<]+)</div>", text)
    if not m:
        # fallback: any occurrence of date pattern
        m = re.search(r"تاريخ النشر:\s*([^<]+)", text)
    if not m:
        return None
    date_str = m.group(1).strip()
    return parse_arabic_date(date_str)

def main():
    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'urls_custom', 'alhaya-ps.tsv'))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    # Wayback CDX query
    cdx_url = ('https://web.archive.org/cdx/search/cdx?url=www.alhaya.ps/ar/Article/*'
               '&from=20260925&to=20261025&output=json&collapse=urlkey')
    status, cdx_text, _ = fetch(cdx_url)
    if status != 200:
        print('Failed to fetch CDX')
        sys.exit(1)
    try:
        cdx_data = json.loads(cdx_text)
    except Exception as e:
        print('CDX JSON parse error', e)
        sys.exit(1)
    # first row is header
    rows = cdx_data[1:]
    urls = [row[2] for row in rows]
    unique_urls = []
    seen = set()
    for u in urls:
        if u not in seen:
            seen.add(u)
            unique_urls.append(u)
    results = []
    counts = collections.Counter()
    for url in unique_urls:
        if url.endswith('/'):
            url = url.rstrip('/')
        pub_date = fetch_article_date(url)
        if not pub_date:
            continue
        if pub_date < START_DATE or pub_date > END_DATE:
            continue
        results.append((url, pub_date.isoformat()))
        counts[pub_date] += 1
        # Check early stop condition
        if all(counts[d] >= MIN_PER_DAY for d in TARGET_DATES):
            break
        # Polite delay
        time.sleep(1)
    # Write TSV
    with open(out_path, 'w', encoding='utf-8') as f:
        for url, d in results:
            f.write(f"{url}\t{d}\n")
    # Print per‑day summary
    for d in sorted(set([date for _, date in results])):
        cnt = sum(1 for _, date in results if date == d)
        print(f"{d}: {cnt} URLs")

if __name__ == '__main__':
    main()
