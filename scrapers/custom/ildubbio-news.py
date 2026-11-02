#!/usr/bin/env python3
"""Il Dubbio (ildubbio.news) - article URLs published 2026-09-25 .. 2026-10-25.

Route: the site's own archive listings, which carry an explicit publication
date per item:
    https://www.ildubbio.news/archivio/<section_id>/<slug>?page=N
Each page holds up to 52 items, newest first, and every item has
    <p class="ora_pubblicazione"><a href="URL">DD.MM.YYYY</a></p>
so the listed date is the date the site itself states on the listing page.

robots.txt allows /archivio/ (it only disallows /sezioni/<n>/<admin-ish slugs>,
/!panel/, /tempcache/, /webservices/). The Google-News sitemap
(siteMapNews.jsp) only holds the current day (16 urls), and the per-section
sitemaps carry no dates, hence the archive listings.

We walk pages of every content section, newest first, and stop for a section
once a whole page is older than the window start.
"""

import os
import re
import sys
import datetime
from collections import Counter, OrderedDict

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scrapers"))
from polite_fetch import fetch  # noqa: E402

BASE = "https://www.ildubbio.news"
OUT = "data/urls_custom/ildubbio-news.tsv"

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

# section id, slug  (order: highest volume first)
SECTIONS = [
    (934, "politica"),
    (926, "cronache"),
    (992, "giustizia"),
    (927, "cultura"),
    (922, "attualita"),
    (995, "interviste"),
    (996, "commenti"),
    (994, "carcere"),
    (993, "avvocatura"),
    (1000, "focus"),
    (1024, "camera-con-vista"),
    (1025, "dossier"),
    (1026, "lato-umano"),
    (1027, "viceversa"),
    (1043, "occhio-al-tech"),
    (1042, "dillo-al-dubbio"),
]
MAX_PAGES = 25       # per section
EXCLUDE = ("/news/video/", "/news/foto/", "/news/podcast/")

ITEM_RE = re.compile(
    r'<p class="ora_pubblicazione"><a href="([^"]+)"[^>]*>\s*([0-9]{1,2})\.([0-9]{1,2})\.([0-9]{4})\s*<'
)
ARTICLE_RE = re.compile(r"^https://www\.ildubbio\.news/news/[a-z0-9\-]+/\d+/[^/]+\.html$")


def parse_page(text):
    """[(url, date)] in page order (newest first)."""
    out = []
    for url, d, m, y in ITEM_RE.findall(text or ""):
        try:
            dt = datetime.date(int(y), int(m), int(d))
        except ValueError:
            continue
        out.append((url, dt))
    return out


def main():
    found = OrderedDict()  # url -> date
    reqs = 0
    for sid, slug in SECTIONS:
        pages_used = 0
        for page in range(1, MAX_PAGES + 1):
            url = f"{BASE}/archivio/{sid}/{slug}?page={page}"
            try:
                status, text, _ = fetch(url)
            except Exception as exc:  # network hiccup: stop this section
                print(f"  ! {slug} p{page} error {exc}", flush=True)
                break
            reqs += 1
            pages_used += 1
            if status != 200 or not text:
                break
            items = parse_page(text)
            if not items:
                break
            new = 0
            for u, dt in items:
                if not ARTICLE_RE.match(u):
                    continue
                if u in found:
                    continue
                found[u] = dt
                new += 1
            dates = [dt for _, dt in items]
            if new == 0:
                break
            if max(dates) < START:          # whole page older than window
                break
            if len(items) < 52:             # last page of the section
                break
        print(f"  {slug:18s} pages={pages_used}", flush=True)

    rows = [(u, dt) for u, dt in found.items() if START <= dt <= END]
    rows.sort(key=lambda r: (r[1], r[0]), reverse=True)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        for u, dt in rows:
            fh.write(f"{u}\t{dt.isoformat()}\n")
    os.replace(tmp, OUT)

    per_day = Counter(dt.isoformat() for _, dt in rows)
    print(f"requests={reqs} urls={len(rows)} -> {OUT}")
    for day in sorted(per_day):
        print(f"  {day}  {per_day[day]}")


if __name__ == "__main__":
    main()
