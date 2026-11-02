#!/usr/bin/env python3
"""clubz.bg scraper.

Route (probed 2026-10-25):
- robots.txt (200) allows everything except /cms/ and /work/.
- No sitemap (sitemap.xml, sitemap_index.xml, sitemapindex.xml, sitemap all 404).
- RSS feed at https://clubz.bg/rss.xml (200) but only ~2.5 days of items (~95).
- Article URLs are sequential integer IDs: https://clubz.bg/<id> (optionally /<id>-slug);
  ~20-40 articles/day, IDs strictly increasing with time (verified against the feed).
- Each article page embeds JSON-LD with "datePublished": "YYYY-MM-DDTHH:MM:SS+ZZ:00"
  (the site-stated publication date) plus a human <span class="date">.

So: read the feed for the newest ID, probe anchor IDs (step -150) until we pass the
window start, then crawl the full ID range sequentially, keep articles whose
site-stated date falls inside 2026-09-25..2026-10-25, dedupe, write TSV.
~1100-1300 requests total at polite_fetch's 2 req/s cap -> ~10-12 min.
"""
import sys, re, json, datetime
from pathlib import Path

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scrapers"))
from polite_fetch import fetch

BASE = "https://clubz.bg"
START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)
OUT = Path("data/urls_custom/clubz-bg.tsv")

MONTHS = {'януари': 1, 'февруари': 2, 'март': 3, 'април': 4, 'май': 5, 'юни': 6,
          'юли': 7, 'август': 8, 'септември': 9, 'октомври': 10, 'ноември': 11, 'декември': 12}

def page_date(html):
    """Site-stated publication date from the article page, or None."""
    m = re.search(r'"datePublished"\s*:\s*"(\d{4})-(\d{2})-(\d{2})', html)
    if m:
        try:
            return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    m = re.search(r'<span class="date">\s*(\d{1,2})\s+([\u0430-\u044f]+)\s+(\d{4})', html)
    if m:
        mo = MONTHS.get(m.group(2).lower())
        if mo:
            try:
                return datetime.date(int(m.group(3)), mo, int(m.group(1)))
            except ValueError:
                return None
    return None

def article_date(url):
    st, text, _ = fetch(url)
    if st != 200 or not text:
        return st, None
    return st, page_date(text)

# --- 1) newest known ID from the feed --------------------------------------
st, feed, _ = fetch(BASE + "/rss.xml")
if st != 200:
    print("feed failed", st)
    sys.exit(1)
ids = [int(m) for m in re.findall(r'https://clubz\.bg/(\d{5,})', feed)]
latest = max(ids)
print("feed:", st, "items:", len(ids), "newest id:", latest)

# --- 2) probe anchor IDs downward to find the window's lower boundary -------
lo = latest
probe = latest
found_below = 0
while probe > latest - 6000 and found_below < 2:
    probe -= 150
    st, d = article_date(f"{BASE}/{probe}")
    if d is None:
        print(f"probe {probe}: no date (status {st})")
        continue
    print(f"probe {probe}: {d}")
    if d < START:
        found_below += 1
        lo = probe
    # keep probing below the start until 2 consecutive below, in case of gaps
if found_below == 0:
    print("WARNING: never reached below window start; extending to latest-6000")
    lo = latest - 6000
lo = max(lo - 150, latest - 6000)  # one step of slack
print("crawling id range", lo, "..", latest, f"({latest - lo + 1} ids)")

# --- 3) sequential crawl -----------------------------------------------------
results = {}   # url -> date
for i in range(lo, latest + 1):
    url = f"{BASE}/{i}"
    st, d = article_date(url)
    if d and START <= d <= END:
        results[url] = d
    if (i - lo) % 200 == 0:
        print(f"  progress {i - lo}/{latest - lo + 1} kept={len(results)}", flush=True)

# --- 4) write TSV ------------------------------------------------------------
OUT.parent.mkdir(parents=True, exist_ok=True)
seen = set()
with open(OUT, "w", encoding="utf-8") as f:
    for url, d in sorted(results.items(), key=lambda kv: (kv[1], kv[0])):
        if url in seen:
            continue
        seen.add(url)
        f.write(f"{url}\t{d.isoformat()}\n")

from collections import Counter
c = Counter(d.isoformat() for d in results.values())
for day in sorted(c):
    print(day, c[day])
print("total written:", len(seen))
