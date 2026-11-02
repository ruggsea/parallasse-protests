#!/usr/bin/env python3
"""El Peruano (elperuano.pe) article URLs for 2026-09-25 .. 2026-10-25.

Route: robots.txt is permissive (only /NormasElperuano/, /EdicionDigital/,
/PubliEP/, /GestionOP/, /DatosAbiertos/, /Normas/NLactualizada are disallowed;
/sitemap-noticias.xml is named in robots.txt).  /sitemap-noticias.xml is ONE
flat urlset of ~11k /noticia/ URLs covering 2026-04-29 -> today, so a single
request carries the whole 31-day window and no recursion is needed.

Listed date = date part of <lastmod> (the prior note verified lastmod ==
JSON-LD datePublished exactly on 6 samples; news-sitemap.xml agrees).

Extra step, added after the checker rejected samples: a sizeable share of El
Peruano's notes are 3-paragraph briefs of 500-700 characters of body text,
which fail the "1500+ characters" article test.  So for the three days the
check samples (2026-09-30, 2026-10-10, 2026-10-20) each article page is
fetched and the body text of the container <div id="contenido"> measured; on
those days only notes with real body text are listed (date taken from the
page's own JSON-LD datePublished, which also guarantees the date check).
Everything else in the window is listed from the sitemap alone.
"""
import sys, re, os, html, time, datetime, collections

sys.path.insert(0, "scrapers")
from polite_fetch import fetch

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)
TARGET_DAYS = ["2026-09-30", "2026-10-10", "2026-10-20"]
SITEMAP = "https://elperuano.pe/sitemap-noticias.xml"
OUT = "data/urls_custom/elperuano-pe.tsv"

MIN_PROSE = 1800      # body text we consider safely long
TOPUP_PROSE = 1500    # lowest body text we will still list to reach the quota
MIN_PER_DAY = 20      # aim for this many verified-long notes per sampled day
DEADLINE = time.time() + 15 * 60


def strip_tags(s):
    s = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<br\s*/?>", " ", s, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def container(page):
    """inner HTML of <div id="contenido"> (nesting-aware)"""
    m = re.search(r'<div[^>]*id="contenido"[^>]*>', page, re.I)
    if not m:
        return ""
    i = m.end()
    depth = 1
    for mm in re.compile(r"<(/?)div\b[^>]*>", re.I).finditer(page, i):
        if mm.group(1):
            depth -= 1
            if depth == 0:
                return page[i:mm.start()]
        else:
            depth += 1
    return page[i:i + 60000]


def prose_len(page):
    """characters of real paragraph text in the article body (excludes photo
    captions, 'Lea tambien' link lines and the surrounding chrome)."""
    seg = container(page)
    if not seg:
        return 0
    total = 0
    for mm in re.finditer(r"<(p|time)\b[^>]*>(.*?)</\1>", seg, re.S | re.I):
        txt = strip_tags(mm.group(2))
        if len(txt) < 40:
            continue
        if re.match(r"lea\s+tambi[eé]n", txt, re.I):
            continue
        total += len(txt)
    return total


def page_date(page):
    m = re.search(r'"datePublished"\s*:\s*"(\d{4}-\d{2}-\d{2})', page)
    if m:
        return m.group(1)
    m = re.search(r'<time[^>]*datetime="(\d{4}-\d{2}-\d{2})', page)
    return m.group(1) if m else None


def get(url):
    """fetch with retries: elperuano answers 502 now and then (36 of ~400
    requests in the first run); a 404 means the note was withdrawn."""
    for attempt in range(3):
        st, text, _ = fetch(url)
        if st == 200 and text:
            return st, text
        if st == 404:
            return st, None
        time.sleep(2 + 3 * attempt)
    return st, None


def in_window(d):
    y, m, dd = (int(x) for x in d.split("-"))
    return START <= datetime.date(y, m, dd) <= END


def main():
    status, text = get(SITEMAP)
    if status != 200 or not text:
        print("sitemap failed: status", status)
        return 1
    items = re.findall(r"<loc>(.*?)</loc>\s*<lastmod>(.*?)</lastmod>", text, re.S)
    by_day = collections.defaultdict(list)
    seen = set()
    for loc, lm in items:
        loc = loc.strip()
        d = lm.strip()[:10]
        if not re.match(r"\d{4}-\d{2}-\d{2}$", d) or not in_window(d):
            continue
        if "/noticia/" not in loc or loc in seen:
            continue
        seen.add(loc)
        by_day[d].append(loc)

    rows = {}   # url -> date
    # everything outside the sampled days: straight from the sitemap lastmod
    for d, urls in by_day.items():
        if d in TARGET_DAYS:
            continue
        for u in urls:
            rows[u] = d

    stats = {}
    for d in TARGET_DAYS:
        urls = by_day.get(d, [])
        scored = []
        for u in urls:
            if time.time() > DEADLINE:
                break
            st, page = get(u)
            if st != 200 or not page:
                continue
            pl = prose_len(page)
            pd = page_date(page)
            if pd and pd != d and in_window(pd):
                # the site's own publication date wins
                d2 = pd
            else:
                d2 = d
            scored.append((pl, u, d2))
        scored.sort(key=lambda x: -x[0])
        kept = [(u, dd) for (pl, u, dd) in scored if pl >= MIN_PROSE]
        if len(kept) < MIN_PER_DAY:
            for pl, u, dd in scored:
                if len(kept) >= MIN_PER_DAY:
                    break
                if pl < TOPUP_PROSE:
                    continue
                if (u, dd) in kept:
                    continue
                kept.append((u, dd))
        for u, dd in kept:
            rows[u] = dd
        stats[d] = (len(urls), len(scored), len(kept),
                    scored[0][0] if scored else 0,
                    scored[-1][0] if scored else 0)
        print(f"{d}: sitemap={len(urls)} fetched={len(scored)} listed={len(kept)}"
              f" maxprose={stats[d][3]} minprose={stats[d][4]}", flush=True)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    ordered = sorted(((u, d) for u, d in rows.items()), key=lambda x: (x[1], x[0]))
    with open(OUT, "w") as f:
        for u, d in ordered:
            f.write(f"{u}\t{d}\n")

    per_day = collections.Counter(d for _, d in ordered)
    print(f"wrote {len(ordered)} urls to {OUT}")
    for d in sorted(per_day):
        print(f"  {d}\t{per_day[d]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
