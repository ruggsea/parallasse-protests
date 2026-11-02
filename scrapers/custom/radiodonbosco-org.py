#!/usr/bin/env python3
"""Radio Don Bosco (Madagascar) - article URLs published 2026-09-25 .. 2026-10-25.

The historic domain radiodonbosco.org no longer serves the outlet: every path
(/, /robots.txt, /sitemap.xml) returns HTTP 200 with the same 76 KB Indonesian
togel spam page, and the Wayback Machine holds only 301 captures of the bare
homepage for 2026 (no article captures at all). The outlet itself moved to
https://www.rdb.mg (Joomla 3.10, Malagasy/French, same station, same articles:
"Vaovaon'ny RDB", "Miara-dalana", ...). So the scraper reads rdb.mg.

Route: Joomla has no sitemap extension (/sitemap.xml, osmap and jmap all 404)
and no API (/api/index.php/v1/... 404, Joomla 3 has none). robots.txt is a 404
-> treated as open. What works is the category blog listing with Joomla
pagination (?start=N, 4 items per page), where every item carries
<time itemprop="datePublished" datetime="..."> - the same tag, with the same
value, that the article page itself prints. So the listed date is the site's
own publication date, taken from the listing, no per-article fetch needed.

Output: data/urls_custom/radiodonbosco-org.tsv, "URL<TAB>YYYY-MM-DD".
"""
import re
import sys
from datetime import date, datetime, timezone

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

BASE = "https://www.rdb.mg"
OUT = "data/urls_custom/radiodonbosco-org.tsv"
START = date(2026, 9, 25)
END = date(2026, 10, 25)

# Section blogs of the site (menu "Fandaharana"/"Vaovao" entries are the same
# articles under /fandaharana/..., so the content paths are used directly).
CATS = [
    "/filazam-baovao/vaovaon-ny-rdb.html",
    "/filazam-baovao/miara-dalana.html",
    "/filazam-baovao/arofanina.html",
    "/filazam-baovao/vatican-news.html",
    "/filazam-baovao/zenit.html",
    "/fanabeazana/ampela-mihary.html",
    "/fanabeazana/andriano-ny-fahasalamana.html",
    "/fanabeazana/hirika.html",
    "/fanabeazana/mba-ho-vanona.html",
    "/fanabeazana/miaina-sy-mitia.html",
    "/fanabeazana/tontolo-meva.html",
    "/pastoraly/finoana-aina.html",
    "/pastoraly/hono-hoy-aho-mompera.html",
    "/pastoraly/kintan-ny-finoana.html",
    "/pastoraly/raki-tsarobidy.html",
    "/pastoraly/tenin-ny-tompo.html",
    "/pastoraly/vakiteny-isan-andro.html",
    "/pastoraly/vatsim-panahy.html",
    "/kolontsaina/filira.html",
    "/kolontsaina/tantara.html",
    "/tontolo-salezianina/afrika-sy-magadasikara.html",
    "/tontolo-salezianina/provdsy-mdg.html",
    "/tontolo-salezianina/sdb-maneran-tany.html",
]

LINK_RE = re.compile(r'<a href="([^"]+)" itemprop="url"')
TIME_RE = re.compile(r'<time datetime="([^"]+)"[^>]*itemprop="datePublished"')
ART_RE = re.compile(r"/\d{5,}-[^/]+\.html$")
PAGE_SIZE = 4
MAX_PAGES_PER_CAT = 40


def parse_listing(html):
    """[(url_path, iso_datetime)] for every blog item on the page, in order."""
    out = []
    for m in LINK_RE.finditer(html):
        path = m.group(1)
        tm = TIME_RE.search(html, m.end(), m.end() + 6000)
        if not tm:
            continue
        out.append((path, tm.group(1)))
    return out


def iso_to_date(iso):
    try:
        return datetime.fromisoformat(iso).date()
    except ValueError:
        return datetime.strptime(iso[:10], "%Y-%m-%d").date()


def norm(url):
    u = url.split("#")[0]
    if u.startswith("http"):
        u = re.sub(r"^https?://(?:www\.)?rdb\.mg", "", u)
    if not u.startswith("/"):
        u = "/" + u
    return BASE + u


def crawl_cat(cat, seen, found):
    for page in range(MAX_PAGES_PER_CAT):
        url = BASE + cat + ("?start=%d" % (page * PAGE_SIZE) if page else "")
        status, text, _ = fetch(url)
        if status != 200 or not text:
            print("  %s start=%d -> HTTP %s, stop" % (cat, page * PAGE_SIZE, status))
            return
        items = parse_listing(text)
        if not items:
            return
        new = 0
        oldest = None
        for path, iso in items:
            if not ART_RE.search(path.split("?")[0]):
                continue
            d = iso_to_date(iso)
            if oldest is None or d < oldest:
                oldest = d
            if not (START <= d <= END):
                continue
            u = norm(path)
            if u in found:
                continue
            new += 1
            found[u] = d
        if oldest is None or oldest < START:
            return
        if new == 0 and page > 0:
            # Joomla clamps start beyond the last page: same content again.
            return


def main():
    found = {}
    for cat in CATS:
        crawl_cat(cat, None, found)

    rows = sorted(found.items(), key=lambda kv: (kv[1], kv[0]))
    with open(OUT, "w") as f:
        for u, d in rows:
            f.write("%s\t%s\n" % (u, d.isoformat()))

    per_day = {}
    for u, d in rows:
        per_day[d.isoformat()] = per_day.get(d.isoformat(), 0) + 1
    print("wrote %d URLs to %s" % (len(rows), OUT))
    day = START
    from datetime import timedelta
    while day <= END:
        k = day.isoformat()
        print("  %s\t%d" % (k, per_day.get(k, 0)))
        day += timedelta(days=1)


if __name__ == "__main__":
    main()
