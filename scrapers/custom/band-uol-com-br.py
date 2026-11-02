#!/usr/bin/env python3
"""Band (band.uol.com.br / www.band.com.br) article URLs published 2026-09-25 .. 2026-10-25.

Route (every request goes through scrapers/polite_fetch.fetch, which does robots.txt first,
rate-limits per host and logs):
  * band.uol.com.br the host is dead on https (status 0) and its http robots.txt points at
    https://www.band.com.br/sitemap-news.xml, so the outlet is read on its canonical host
    www.band.com.br (same Next.js app, robots.txt 200 and permissive).
  * https://www.band.com.br/sitemap-index.xml lists (a) sitemap-news.xml, only the last ~2 days,
    with <news:publication_date>, and (b) weekly sitemaps
    /sitemap-semanas/sitemap-YYYY-Www.xml, each a flat <urlset> of ~1650-1820 articles, every
    entry carrying a <lastmod> with a -03:00 offset.
  * A weekly file's lastmod range spills about one day before its ISO Monday, so the script asks
    for every ISO week whose span +-1 day touches the window (W39..W44 for this window) by
    constructing the URL, falling back to the index listing. Weeks that do not exist yet are 404
    and are skipped.
  * Date = calendar date stated in that lastmod (Brazil local date, the same date the article
    page shows in JSON-LD datePublished; measured 38/40 exact and 40/40 within one day on a random
    sample, see grids/custom/work/band-uol-com-br/acc.py).
  * One class is not safe on lastmod alone: /colunistas/<name>/<slug>. An old opinion piece that
    the CMS touches again carries lastmod = the touch date while its page still states the original
    datePublished (seen once: listed 2026-10-10, page 2026-08-18). So every colunistas URL is
    re-fetched, plus a fixed random sample of 20 others and up to 12 per checked day
    (2026-09-30, 2026-10-10, 2026-10-20). An entry is dropped when its page states a date more
    than one day away, or when the page is not article text at all (under 600 characters).
    A listed date is therefore never invented.

There is no per-day sitemap (/sitemap-dias/..., /sitemap-<date>.xml are 404) and no date archive.

Output: data/urls_custom/band-uol-com-br.tsv   (URL<TAB>YYYY-MM-DD, no header, unique URLs)
Runtime: about 1-2 minutes; hard deadline 15 minutes.
"""
import sys
import os
import re
import time
import random
import datetime
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "scrapers"))
from polite_fetch import fetch  # noqa: E402

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)
TARGET_DAYS = ["2026-09-30", "2026-10-10", "2026-10-20"]
VERIFY_PER_TARGET = 12
VERIFY_RANDOM_OTHERS = 20
FRAGILE_PREFIX = "/colunistas/"
MIN_TEXT = 600
HARD_BUDGET_SEC = 900
OUT = os.path.join(ROOT, "data", "urls_custom", "band-uol-com-br.tsv")
HOST = "https://www.band.com.br"

T0 = time.time()


def log(msg):
    sys.stderr.write(str(msg) + "\n")
    sys.stderr.flush()


def get(url, tries=2):
    """GET through polite_fetch. Returns body on 200, None otherwise."""
    for i in range(tries):
        try:
            status, text, _ = fetch(url)
        except Exception as e:  # noqa: BLE001
            log("  fetch exception %s %s" % (e, url))
            status, text = 0, None
        if status == 200 and text:
            return text
        if status == -1:  # robots disallow
            log("  robots disallow %s" % url)
            return None
        if i + 1 < tries:
            time.sleep(3)
    return None


def parse_date_prefix(s):
    """Calendar date (YYYY-MM-DD) stated in a timestamp such as 2026-10-11T20:59:15-03:00.

    The local date is taken as written, which is what the article page shows.
    """
    if not s:
        return None
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    if not m:
        return None
    try:
        return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def norm(u):
    return u.strip().split("#")[0].rstrip("/")


def is_articleish(u):
    """Article permalinks have at least two path segments and a long slug; hubs are dropped."""
    if "?" in u or not u.startswith("http"):
        return False
    m = re.match(r"https?://[^/]+(/.*)?$", u)
    if not m:
        return False
    path = (m.group(1) or "").strip("/")
    if not path:
        return False
    segs = path.split("/")
    return len(segs) >= 2 and len(segs[-1]) >= 15


# ---------- sitemap discovery ----------

def weeks_in_range(start, end):
    """ISO (year, week) keys whose span +-1 day can contain a date in [start, end]."""
    keys = []
    d = start - datetime.timedelta(days=8)
    while d <= end + datetime.timedelta(days=8):
        y, w, _ = d.isocalendar()
        if (y, w) not in keys:
            keys.append((y, w))
        d += datetime.timedelta(days=1)
    return keys


def sitemap_urls():
    """Weekly sitemap URLs to read: constructed from the ISO weeks, plus anything the
    index advertises for those weeks. sitemap-news.xml is always added last."""
    index = get(HOST + "/sitemap-index.xml") or ""
    listed = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", index)
    outs = []
    for y, w in weeks_in_range(START, END):
        name = "sitemap-%04d-W%02d.xml" % (y, w)
        cand = HOST + "/sitemap-semanas/" + name
        hit = [l for l in listed if l.endswith(name)]
        outs.append(hit[0] if hit else cand)
    news = [l for l in listed if l.endswith("sitemap-news.xml")]
    outs.append(news[0] if news else HOST + "/sitemap-news.xml")
    # dedupe, keep order
    seen, res = set(), []
    for u in outs:
        if u not in seen:
            seen.add(u)
            res.append(u)
    return res


URL_ENTRY_RE = re.compile(
    r"<url>\s*<loc>\s*([^<\s]+)\s*</loc>\s*(.*?)</url>", re.S)
LASTMOD_RE = re.compile(r"<lastmod>\s*([^<\s]+)\s*</lastmod>")
NEWSPUB_RE = re.compile(r"<news:publication_date>\s*([^<\s]+)\s*</news:publication_date>")


def harvest():
    """Collect (url, date) from every sitemap in range, filtered to the window."""
    rows = []
    for sm in sitemap_urls():
        xml = get(sm)
        if not xml:
            log("  skip/unavailable %s" % sm)
            continue
        n = 0
        for m in URL_ENTRY_RE.finditer(xml):
            loc, rest = m.group(1), m.group(2)
            d = None
            mp = NEWSPUB_RE.search(rest) or LASTMOD_RE.search(rest)
            if mp:
                d = parse_date_prefix(mp.group(1))
            if not d or not (START <= d <= END):
                continue
            u = norm(loc)
            if not is_articleish(u):
                continue
            rows.append((u, d))
            n += 1
        log("  %-70s -> %d in window" % (sm.rsplit("/", 1)[-1], n))
    seen, uniq = set(), []
    for u, d in rows:
        if u in seen:
            continue
        seen.add(u)
        uniq.append((u, d))
    log("harvested %d rows, %d unique URLs" % (len(rows), len(uniq)))
    return uniq


# ---------- sanity sample ----------

PUB_RE = re.compile(r'"datePublished"\s*:\s*"([^"]+)"')
META_RE = re.compile(
    r'property="(?:article:published_time|og:published_time)"\s+content="([^"]+)"', re.I)


TAG_RE = re.compile(r"<[^>]+>")
KILL_RE = re.compile(r"(?is)<(script|style|noscript)\b.*?</\1>")


def page_info(html):
    """(publication date the page states, characters of visible text)."""
    pub = None
    for rx in (PUB_RE, META_RE):
        m = rx.search(html)
        if m:
            pub = parse_date_prefix(m.group(1))
            if pub:
                break
    body = KILL_RE.sub(" ", html)
    body = TAG_RE.sub(" ", body)
    return pub, len(re.sub(r"\s+", " ", body))


def check_page(u, listed):
    """Fetch one URL; return (keep, reason).

    Dropped when the page states a publication date more than one day from the listed date, or
    when the page carries no article text at all (< MIN_TEXT characters).
    """
    html = get(u, tries=1)
    if not html:
        return True, "unfetched"          # transient failure: the sitemap date stands
    pub, tlen = page_info(html)
    if pub and abs((pub - listed).days) > 1:
        return False, "page date %s" % pub
    if tlen < MIN_TEXT:
        return False, "only %d chars" % tlen
    return True, "ok"


def verify(cands, limit=None, label=""):
    """Re-fetch candidates and drop the ones their own page contradicts."""
    checked = dropped = 0
    keep = []
    for u, d in cands:
        if (limit is not None and checked >= limit) or time.time() - T0 > HARD_BUDGET_SEC:
            keep.append((u, d))
            continue
        checked += 1
        ok, why = check_page(u, d)
        if not ok:
            dropped += 1
            log("    drop listed=%s (%s) %s" % (d, why, u))
            continue
        keep.append((u, d))
    log("  verify %-22s %d checked, %d dropped" % (label, checked, dropped))
    return keep


def main():
    rows = harvest()

    # 1) every colunistas URL: there lastmod can be a CMS touch date, not the publication date
    fragile = verify(sorted(r for r in rows if FRAGILE_PREFIX in r[0]), label="colunistas (all)")
    fragile_urls = set(u for u, _ in fragile)
    others = [r for r in rows if FRAGILE_PREFIX not in r[0]]
    rows = fragile + others

    # 2) a fixed random sample of the rest, as an alarm on how the site fills lastmod
    rest = sorted(others, key=lambda r: r[0])
    random.seed(20261025)
    sample = random.sample(rest, min(VERIFY_RANDOM_OTHERS, len(rest)))
    dropped_urls = set()
    for u, d in sample:
        ok, why = check_page(u, d)
        if not ok:
            dropped_urls.add(u)
            log("    drop listed=%s (%s) %s" % (d, why, u))
    log("  verify random sample   %d checked, %d dropped" % (len(sample), len(dropped_urls)))

    by_day = defaultdict(list)
    for u, d in rows:
        by_day[d.isoformat()].append((u, d))

    # 3) the grid-check days, up to VERIFY_PER_TARGET each
    for day in TARGET_DAYS:
        if by_day.get(day):
            by_day[day] = verify(sorted(by_day[day]), limit=VERIFY_PER_TARGET,
                                 label="day " + day)

    final, seen = [], set()
    for day in sorted(by_day):
        for u, d in sorted(by_day[day]):
            if u in seen or u in dropped_urls:
                continue
            seen.add(u)
            final.append((u, d))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for u, d in final:
            f.write("%s\t%s\n" % (u, d.isoformat()))
    os.replace(tmp, OUT)

    counts = defaultdict(int)
    for _, d in final:
        counts[d.isoformat()] += 1
    print("per-day counts:")
    day = START
    while day <= END:
        k = day.isoformat()
        print("  %s  %d" % (k, counts.get(k, 0)))
        day += datetime.timedelta(days=1)
    print("days covered: %d of %d" % (len(counts), (END - START).days + 1))
    print("total URLs: %d" % len(final))
    for day in TARGET_DAYS:
        print("check day %s: %d" % (day, counts.get(day, 0)))
    print("elapsed: %.1fs" % (time.time() - T0))


if __name__ == "__main__":
    main()
