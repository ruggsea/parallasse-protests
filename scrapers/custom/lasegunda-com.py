#!/usr/bin/env python3
"""La Segunda (lasegunda.com, Chile) URL lister for 2026-09-25..2026-10-25.

Route (status codes as observed 2026-10-27):
  * https://www.lasegunda.com/robots.txt                       200, permissive
    for `User-agent: *` (only /bin/, /Controls/, /Data/, /Detalle/, /Plantillas/,
    /xmlpandora/, /Registro/ disallowed; our UA is not in the named-bot list).
    It names one sitemap: https://www.lasegunda.com/sitemap/sitemap.xml
  * sitemap index                                               200 -> 199
    urlset entries, one per section per year: /sitemap/xml/sitemap<N>_<YYYY>.xml
    (13 files exist for 2026, ~5.6k URLs for the whole year).
    The <lastmod> values are all the sitemap *generation* time (identical
    timestamp on every entry), so they are useless as publish dates.
  * per-section urlset files                                     200, but the
    <url> blocks carry ONLY <loc>: no <lastmod>, no news:publication_date.
    The URL path has year/month and the article id but NOT the day
    (/Noticias/Politica/2026/10/1116483/<slug>), so the sitemap alone cannot
    date an article.
  * Every other sitemap path tried (/sitemap/news.xml, /news-sitemap.xml,
    /sitemap-news.xml, /sitemap/xml/news_2026.xml, ...) returns the site's
    31720-byte soft-404 HTML page: there is no Google-News sitemap.
  * Article page                                                200, ~26 KB,
    ~10 KB of text, and it carries the publication date in the inline script
    `var rts_date = 'DD-MM-YYYY'; var rts_time = 'HH:MM:SS';` (Santiago local
    time). Verified on 6 pages. That variable is authoritative and is what we
    list.

So: sitemap index -> the 13 per-section 2026 urlsets -> keep the September and
October candidates (numeric ids are monotonically increasing, so the tail of
September is enough; everything from October 1 on is kept) -> fetch those
article pages in a small thread pool through polite_fetch (per-host rate limit
is enforced by polite_fetch itself) -> read rts_date -> keep 09-25..10-25.

Fallbacks for the date if rts_date is missing: JSON-LD datePublished,
<meta property="article:published_time">, then the /Fotos/YYYY/MM/DD/ image
path, which is the day the image was uploaded and matched rts_date on every
page checked.

Run: python3 scrapers/custom/lasegunda-com.py
"""
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

INDEX = "https://www.lasegunda.com/sitemap/sitemap.xml"
OUT = "data/urls_custom/lasegunda-com.tsv"
START, END = "2026-09-25", "2026-10-25"
DEADLINE = time.time() + 16 * 60  # hard stop well inside the 20 min budget
WORKERS = 4

# September tail: ids grow with time, ~19 articles/day, so the last 220
# September-path URLs cover ~11 days before the month end (enough margin).
SEPT_TAIL = 220

LOC_RE = re.compile(r"<loc>\s*(.*?)\s*</loc>", re.S)
ID_RE = re.compile(r"/(\d{6,})/")
MONTH_RE = re.compile(r"/(\d{4})/(\d{2})/")
RTS_DATE_RE = re.compile(r"rts_date\s*=\s*'([0-9]{2}-[0-9]{2}-[0-9]{4})'")
JSONLD_RE = re.compile(r'"datePublished"\s*:\s*"([0-9]{4}-[0-9]{2}-[0-9]{2})')
PUBTIME_RE = re.compile(
    r'property="article:published_time"\s*content="([0-9]{4}-[0-9]{2}-[0-9]{2})')
FOTO_RE = re.compile(r"/Fotos/(\d{4})/(\d{2})/(\d{2})/")


def norm(url):
    url = url.split("?")[0].split("#")[0].rstrip("/")
    if url.startswith("http://"):
        url = "https://" + url[len("http://"):]
    return url


def sitemap_urls():
    """All candidate article URLs from the 2026 per-section sitemaps."""
    st, body, _ = fetch(INDEX)
    if not body:
        print("sitemap index failed", st)
        return []
    maps = [u for u in LOC_RE.findall(body) if "2026" in u]
    print(f"sitemap index: {st}, {len(maps)} urlset files for 2026")
    urls = []
    for sm in maps:
        st2, b2, _ = fetch(sm)
        if not b2:
            print(f"  {sm} -> {st2}")
            continue
        urls.extend(LOC_RE.findall(b2))
    seen, out = set(), []
    for u in urls:
        if not ID_RE.search(u):
            continue
        n = norm(u)
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def date_from_page(body):
    """Publication date as the page states it, or None."""
    m = RTS_DATE_RE.search(body)
    if m:
        d, mo, y = m.group(1).split("-")
        return f"{y}-{mo}-{d}"
    m = JSONLD_RE.search(body)
    if m:
        return m.group(1)
    m = PUBTIME_RE.search(body)
    if m:
        return m.group(1)
    m = FOTO_RE.search(body)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return None


def main():
    cand = sitemap_urls()
    if not cand:
        print("no candidates from sitemaps")
        return 1
    sept = sorted([u for u in cand if MONTH_RE.search(u).group(2) == "09"],
                  key=lambda u: int(ID_RE.search(u).group(1)))
    octo = sorted([u for u in cand if MONTH_RE.search(u).group(2) == "10"],
                  key=lambda u: int(ID_RE.search(u).group(1)))
    todo = sept[-SEPT_TAIL:] + octo
    print(f"candidates: {len(cand)} total, {len(sept)} in Sept, "
          f"{len(octo)} in Oct -> fetching {len(todo)} article pages "
          f"with {WORKERS} workers")

    results = {}
    done = [0]

    def work(url):
        if time.time() > DEADLINE:
            return
        try:
            st, body, _ = fetch(url)
        except Exception:
            return
        done[0] += 1
        if done[0] % 100 == 0:
            print(f"  {done[0]} fetched, {len(results)} dated, "
                  f"{int(time.time() - t0)}s")
        if not body:
            return
        d = date_from_page(body)
        if d:
            results[url] = d

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        list(pool.map(work, todo))

    rows = [(u, d) for u, d in results.items() if START <= d <= END]
    rows.sort(key=lambda r: (r[1], r[0]))
    import os
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        for u, d in rows:
            f.write(f"{u}\t{d}\n")

    per_day = {}
    for _, d in rows:
        per_day[d] = per_day.get(d, 0) + 1
    print(f"wrote {len(rows)} urls to {OUT} in {int(time.time() - t0)}s")
    for d in sorted(per_day):
        print(f"  {d}\t{per_day[d]}")
    print("days covered:", len(per_day))
    return 0


if __name__ == "__main__":
    sys.exit(main())
