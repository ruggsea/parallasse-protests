#!/usr/bin/env python3
"""noticiasuno-com: article URLs published 2026-09-25 .. 2026-10-25.

Route (probed 2026-10-26/27):
  robots.txt of www.noticiasuno.com is Yoast, `Disallow:` empty -> all paths open,
  Sitemap: https://www.noticiasuno.com/sitemap_index.xml
  The site is WordPress with the REST API open:
    /wp-json/wp/v2/posts?per_page=100&after=2026-09-25T00:00:00&before=2026-10-26T00:00:00
  Only post types: post/page/attachment (+ FSE internals) -> `posts` is the whole news stream.
  The listed date is the REST 'date' field, which is WordPress site-local time
  (America/Bogota, -05:00). It equals the page's own <time datetime="...-05:00"> and the
  date printed on the page ("25 octubre 2026"). The page's meta/JSON-LD
  article:published_time is the same instant expressed in UTC (so it can be one calendar
  day later for these late-night posts); the local date is the one the site states.

  Avoid: Yoast post-sitemap.xml <lastmod> is the last-EDIT time (index lastmod 2026-10-26
  for weeks-old posts), and /sitemap-news.xml only holds the last ~48h. Daily archives
  (/2026/10/10/) 404. So sitemap is only a URL source; dates would have to be re-read from
  each page.

Editorial note: this outlet publishes ONLY on Saturdays, Sundays and holidays
(the TV programme airs those days), 11-13 posts per emission, all timestamped
23:3x-23:5x local. Weekdays (2026-09-30, 2026-10-20) have zero posts, 2026-10-10 (Saturday)
has 13. That is the site's real output, so the run is recorded as low volume.
"""
import json
import re
import sys
import time

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scrapers"))
from polite_fetch import fetch  # noqa: E402

OUT = "data/urls_custom/noticiasuno-com.tsv"
SITE = "https://www.noticiasuno.com"
WINDOW = ("2026-09-25", "2026-10-25")
AFTER = WINDOW[0] + "T00:00:00"
BEFORE = "2026-10-26" + "T00:00:00"
BUDGET_S = 15 * 60


def in_window(d):
    return WINDOW[0] <= d <= WINDOW[1]


def from_rest():
    """Primary: WP REST posts endpoint, paginated. Returns [(link, local_date)]."""
    rows = []
    for page in range(1, 9):
        url = (
            f"{SITE}/wp-json/wp/v2/posts?per_page=100&page={page}"
            f"&after={AFTER}&before={BEFORE}&_fields=date,link"
        )
        status, text, _ = fetch(url)
        if status != 200 or not text:
            print(f"rest page {page}: status {status} -> stop", flush=True)
            break
        try:
            data = json.loads(text)
        except ValueError:
            print(f"rest page {page}: not json -> stop", flush=True)
            break
        if not isinstance(data, list) or not data:
            break
        for item in data:
            link, date = item.get("link"), item.get("date") or ""
            if link and len(date) >= 10:
                rows.append((link, date[:10]))
        print(f"rest page {page}: {len(data)} posts", flush=True)
        if len(data) < 100:
            break
    return rows


def from_sitemap_and_pages(deadline):
    """Fallback: post-sitemap URLs, date read from each page's <time datetime> (site-local)."""
    status, text, _ = fetch(f"{SITE}/post-sitemap.xml")
    if status != 200 or not text:
        print(f"sitemap fallback: status {status}", flush=True)
        return []
    urls = re.findall(r"<loc>([^<]+)</loc>", text)
    print(f"sitemap fallback: {len(urls)} urls", flush=True)
    rows = []
    for u in urls:
        if time.time() > deadline:
            print("sitemap fallback: time budget reached", flush=True)
            break
        st, body, _ = fetch(u)
        if st != 200 or not body:
            continue
        m = re.search(r'<time[^>]*datetime="(20\d\d-\d\d-\d\d)T', body)
        if m:
            rows.append((u, m.group(1)))
    return rows


def main():
    t0 = time.time()
    rows = from_rest()
    if not rows:
        rows = from_sitemap_and_pages(t0 + BUDGET_S)

    seen = {}
    for link, date in rows:
        if not in_window(date):
            continue
        link = link.split("#")[0]
        seen.setdefault(link, date)

    pairs = sorted(seen.items(), key=lambda kv: (kv[1], kv[0]))
    with open(OUT, "w") as f:
        for link, date in pairs:
            f.write(f"{link}\t{date}\n")

    per_day = {}
    for _, date in pairs:
        per_day[date] = per_day.get(date, 0) + 1
    for d in sorted(per_day):
        print(f"{d}\t{per_day[d]}", flush=True)
    print(f"total {len(pairs)} urls written to {OUT} in {time.time() - t0:.0f}s", flush=True)
    for d in ("2026-09-30", "2026-10-10", "2026-10-20"):
        print(f"target {d}: {per_day.get(d, 0)}", flush=True)


if __name__ == "__main__":
    main()
