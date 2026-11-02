#!/usr/bin/env python3
"""Le Devoir (ledevoir.com) article list for 2026-09-25 .. 2026-10-25.

Route: the site's section listing pages paginate server-side with ?page=N and
each card carries a machine-readable <time datetime="...Z"> (UTC) plus the
article path /<section>[/<sub>]/<id>/<slug>.  robots.txt (User-agent: *) only
disallows /recherche and a few auth paths; sitemap.xml lists sections only
(429 URLs, no articles), sitemap-news.xml holds just the last two days.

So we walk the news sections (top level + subsections) page by page until the
cards are older than the window, and take the date from the card's <time>.
"""
import os
import re
import sys
import time

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scrapers"))
from polite_fetch import fetch  # noqa: E402

ROOT = str(__import__("pathlib").Path(__file__).resolve().parents[2])
OUT = os.path.join(ROOT, "data/urls_custom/ledevoir-com.tsv")

START = "2026-09-25"
END = "2026-10-25"
BASE = "https://www.ledevoir.com"

# Every news section that carries articles, top level first (they yield the
# most per page), then the subsections for depth on quiet days.
SECTIONS = [
    "actualites", "politique", "economie", "monde", "culture", "opinion",
    "plaisirs", "sports",
    "actualites/societe", "actualites/education", "actualites/environnement",
    "actualites/justice", "actualites/sante", "actualites/science",
    "actualites/transports-urbanisme", "actualites/immigration",
    "politique/canada", "politique/quebec", "politique/montreal",
    "politique/ville-de-quebec", "politique/regions",
    "economie/consommation", "economie/finances-personnelles", "economie/techno",
    "monde/afrique", "monde/ameriques", "monde/asie", "monde/etats-unis",
    "monde/europe", "monde/moyen-orient",
    "culture/arts-visuels", "culture/cinema", "culture/danse", "culture/ecrans",
    "culture/medias", "culture/musique", "culture/theatre",
    "opinion/chroniques", "opinion/editoriaux", "opinion/idees",
    "opinion/libre-opinion", "opinion/lettres", "opinion/le-devoir-de",
    "plaisirs/alimentation", "plaisirs/habitation", "plaisirs/restaurant",
    "plaisirs/vin", "plaisirs/voyage", "plaisirs/recettes", "plaisirs/jardinage",
]

MAX_PAGES = 30          # per section
BUDGET_SEC = 13 * 60    # keep the whole run well under the 20 min limit

# A card is <article ...> ... <a class="stretched-link" href="/x/1234567/slug">
# ... <time datetime="2026-10-23T16:00:00Z">.  Parse one chunk per <article>
# so a card without a <time> cannot steal the next card's date.
CHUNK = re.compile(r"<article\b(.*?)</article>", re.S)
HREF = re.compile(r'href="(/[^"?#]*?/\d{6,}/[^"?#]*)"')
TIME = re.compile(r'<time[^>]*datetime="(\d{4}-\d{2}-\d{2})T')


def parse_cards(html):
    out = []
    for chunk in CHUNK.findall(html):
        m = HREF.search(chunk)
        if not m:
            continue
        t = TIME.search(chunk)
        if not t:
            continue
        path = m.group(1)
        if not path.startswith("/"):
            path = "/" + path
        out.append((BASE + path, t.group(1)))
    return out


def main():
    t0 = time.time()
    found = {}          # url -> date
    per_section = []
    for sect in SECTIONS:
        if time.time() - t0 > BUDGET_SEC:
            print("budget exhausted before section", sect, flush=True)
            break
        got = 0
        for page in range(1, MAX_PAGES + 1):
            if time.time() - t0 > BUDGET_SEC:
                break
            url = "%s/%s?page=%d" % (BASE, sect, page)
            try:
                status, body, _ = fetch(url)
            except Exception as exc:                       # noqa: BLE001
                print("ERR %s %s" % (url, exc), flush=True)
                break
            if status != 200 or not body:
                if page == 1:
                    print("skip %s (status %s)" % (sect, status), flush=True)
                break
            cards = parse_cards(body)
            if not cards:
                break
            new = 0
            oldest = "9999-99-99"
            for u, d in cards:
                oldest = min(oldest, d)
                if not (START <= d <= END):
                    continue
                if u not in found:
                    found[u] = d
                    new += 1
                    got += 1
            if new == 0 and page > 1:
                break
            if oldest < START:
                break
        per_section.append((sect, got))
        print("%-34s +%d  (total %d)" % (sect, got, len(found)), flush=True)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    rows = sorted(found.items(), key=lambda kv: (kv[1], kv[0]))
    tmp = OUT + ".tmp"
    with open(tmp, "w") as f:
        for u, d in rows:
            f.write("%s\t%s\n" % (u, d))
    os.replace(tmp, OUT)

    counts = {}
    for _, d in rows:
        counts[d] = counts.get(d, 0) + 1
    print("\nwrote %d unique URLs to %s" % (len(rows), OUT))
    print("per day:")
    for d in sorted(counts):
        print("  %s  %d" % (d, counts[d]))
    print("sections: %d, elapsed %.0fs" % (len(per_section), time.time() - t0))


if __name__ == "__main__":
    main()
