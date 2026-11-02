import sys, os, json, datetime
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# ensure path includes scrapers root for polite_fetch
from polite_fetch import fetch

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

BASE_URL = 'https://2424.mg/wp-json/wp/v2/posts'
PER_PAGE = 100

def iso_to_date(s):
    # s like '2026-10-05T08:02:19'
    return datetime.datetime.fromisoformat(s).date()

def fetch_posts(page=1, after=None, before=None):
    # Build URL with optional date filters
    params = [f'per_page={PER_PAGE}', '_fields=date,link', f'page={page}']
    if after:
        params.append(f'after={after}')
    if before:
        params.append(f'before={before}')
    url = f"{BASE_URL}?{'&'.join(params)}"
    status, text, _ = fetch(url)
    if status != 200:
        raise RuntimeError(f'Failed to fetch page {page}, status {status}')
    return json.loads(text)

def main():
    all_posts = []
    page = 1
    while True:
        try:
            posts = fetch_posts(page)
        except Exception as e:
            print('Error fetching', e, file=sys.stderr)
            break
        if not posts:
            break
        all_posts.extend(posts)
        if len(posts) < PER_PAGE:
            break
        page += 1
    # Filter dates already within range (should be)
    filtered = []
    for p in all_posts:
        d = iso_to_date(p['date'])
        if START <= d <= END:
            filtered.append((p['link'], d.isoformat()))
    # Deduplicate URLs
    seen = set()
    uniq = []
    for url, d in filtered:
        if url not in seen:
            seen.add(url)
            uniq.append((url, d))
    # Write TSV
    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../data/urls_custom/2424-mg.tsv'))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        for url, d in uniq:
            f.write(f"{url}\t{d}\n")
    # Print per‑day counts
    counts = {}
    for _, d in uniq:
        counts[d] = counts.get(d, 0) + 1
    for day in sorted(counts):
        print(f"{day}\t{counts[day]}")
    print('Total', len(uniq), 'URLs written to', out_path)

if __name__ == '__main__':
    main()
