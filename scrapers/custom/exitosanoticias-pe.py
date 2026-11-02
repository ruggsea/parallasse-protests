#!/usr/bin/env python3
"""Exitosa Noticias (exitosanoticias.pe) URL lister for a date window.

Route: the outlet's own "ultimas noticias" listing paginates at
https://www.exitosanoticias.pe/ultimas-noticias/?p=N with 15 <article> cards per
page, newest first, deep pagination (p=130 still answers 200).  Each card carries
the publication date as text: <span class="date"> 26 de Octubre, 2026 </span>.
That listing date equals the article page's JSON-LD datePublished (verified on
samples), so no per-article fetch is needed.

Sitemaps were useless for dates: /sitemapNoticiasYYYYMM.xml lists ~1900 urls per
month with NO <lastmod>; /sitemapNews.xml carries news:publication_date but only
~2 days of articles; /wp-json/wp/v2/ is 404; /feed, /YYYY/MM/DD/ archives and
per-day sitemap files all 404.
"""

import re
import sys
import time
from datetime import date

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

OUT = "data/urls_custom/exitosanoticias-pe.tsv"
START = date(2026, 9, 25)
END = date(2026, 10, 25)

BASE = "https://www.exitosanoticias.pe/ultimas-noticias/?p=%d"
MAX_PAGES = 400
DEADLINE = 15 * 60  # seconds; the whole run must stay well under 20 minutes

MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "setiembre": 9, "septiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}

RE_DATE = re.compile(r"(\d{1,2})\s+de\s+([A-Za-zÁÉÍÓÚáéíóúñ]+),?\s+(\d{4})")
RE_CARD = re.compile(
    r'<article.*?href="(https://www\.exitosanoticias\.pe/[^"#?]+)".*?'
    r'<span class="date">\s*([^<]*?)\s*</span>',
    re.S,
)


def parse_es_date(txt):
    m = RE_DATE.search(txt or "")
    if not m:
        return None
    day, mon, year = m.group(1), m.group(2).lower(), m.group(3)
    num = MESES.get(mon)
    if not num:
        return None
    try:
        return date(int(year), num, int(day))
    except ValueError:
        return None


def main():
    found = {}          # url -> iso date
    t0 = time.time()
    pages = 0
    stop_reason = "reached MAX_PAGES"
    for p in range(1, MAX_PAGES + 1):
        if time.time() - t0 > DEADLINE:
            stop_reason = "deadline"
            break
        status, text, _ = fetch(BASE % p)
        pages += 1
        if status != 200 or not text:
            # retry once, then stop: the listing is contiguous from the top
            time.sleep(2.0)
            status, text, _ = fetch(BASE % p)
            pages += 1
            if status != 200 or not text:
                stop_reason = "status %s at p=%d" % (status, p)
                break
        cards = RE_CARD.findall(text)
        if not cards:
            stop_reason = "no cards at p=%d" % p
            break
        dates = []
        for url, dtxt in cards:
            d = parse_es_date(dtxt)
            if d is None:
                continue
            dates.append(d)
            if START <= d <= END:
                found.setdefault(url.split("?")[0], d.isoformat())
        if not dates:
            stop_reason = "no parseable dates at p=%d" % p
            break
        if max(dates) < START:
            # whole page older than the window: nothing further to gain
            stop_reason = "page older than window at p=%d" % p
            break

    rows = sorted(found.items(), key=lambda kv: (kv[1], kv[0]))
    with open(OUT, "w", encoding="utf-8") as fh:
        for url, d in rows:
            fh.write("%s\t%s\n" % (url, d))

    per_day = {}
    for _, d in rows:
        per_day[d] = per_day.get(d, 0) + 1
    print("pages fetched: %d (%s)" % (pages, stop_reason))
    print("urls written: %d -> %s" % (len(rows), OUT))
    for d in sorted(per_day):
        print("  %s  %3d" % (d, per_day[d]))


if __name__ == "__main__":
    main()
