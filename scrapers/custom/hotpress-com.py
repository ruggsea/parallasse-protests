#!/usr/bin/env python3
import sys, re, datetime
from bs4 import BeautifulSoup

# make polite_fetch importable
import sys as _sys
_sys.path.insert(0, "scrapers")
from polite_fetch import fetch

START = datetime.date(2026, 9, 25)
END   = datetime.date(2026, 10, 25)
BASE  = "https://www.hotpress.com/news"

def parse_date(txt: str) -> datetime.date | None:
    # format: '25 Oct 26'
    try:
        day_s, mon_s, yr_s = txt.strip().split()
        day = int(day_s)
        year = int(yr_s)
        year += 2000 if year < 50 else 1900
        month = datetime.datetime.strptime(mon_s, "%b").month
        return datetime.date(year, month, day)
    except Exception:
        return None

seen = set()
records = []
page = 1
empty_pages = 0
while True:
    url = f"{BASE}/page/{page}" if page > 1 else BASE
    status, html, _ = fetch(url)
    if status != 200:
        print(f"Failed fetch {url}: {status}", file=sys.stderr)
        break
    soup = BeautifulSoup(html, "html.parser")
    # each article has a ul.time-list then an <a href=...>
    for ul in soup.find_all('ul', class_=re.compile('time-list')):
        li_items = ul.find_all('li')
        if len(li_items) < 2:
            continue
        date_txt = li_items[1].get_text(strip=True)
        d = parse_date(date_txt)
        if not d or d < START or d > END:
            continue
        # find the next <a> tag after this ul
        next_a = ul.find_next('a', href=True)
        if not next_a:
            continue
        link = next_a['href']
        if link not in seen:
            seen.add(link)
            records.append((link, d.isoformat()))
    # stop condition: three consecutive pages without new records
    if any(START <= datetime.date.fromisoformat(r[1]) <= END for r in records):
        empty_pages = 0
    else:
        empty_pages += 1
    if empty_pages >= 3 or page >= 50:
        break
    page += 1

# write TSV
out_path = "data/urls_custom/hotpress-com.tsv"
with open(out_path, "w", encoding="utf-8") as f:
    for link, iso in sorted(records, key=lambda x: x[1]):
        f.write(f"{link}\t{iso}\n")

# per‑day summary
from collections import Counter
cnt = Counter([d for _, d in records])
for day in sorted(cnt):
    print(f"{day}: {cnt[day]} URLs")
