#!/usr/bin/env python3
"""Emol (Chile, emol.com) - article URLs published 2026-09-25 .. 2026-10-25.

Route that works
----------------
robots.txt (https://www.emol.com/robots.txt, 200) is permissive for us; the sitemap
index https://www.emol.com/sitemap/sitemapIndex.xml returns 200 and lists per-year
chunks of the form /sitemap/xml/sitemapN_YYYY.xml (e.g. sitemap1_2026.xml ..
sitemap11_2026.xml; eight of them for 2026).  Each chunk is a flat <urlset> of article
URLs

    /noticias/<Section>/YYYY/MM/DD/<id>/<slug>.html

with NO <lastmod>, so the publication date is taken from the /YYYY/MM/DD/ segment of
the path.  Checked against the pages' own <meta property="article:published_time">
on several articles: identical to the path date.

Two traps found the hard way
----------------------------
* Every <loc> in the sitemaps is http://www.emol.com/... and plain HTTP does not
  answer at all (connection error / polite_fetch status 0, 0 bytes).  HTTPS does
  (200, ~120 KB).  So every URL is emitted with the https:// scheme.
* Non-existent sitemap shards (sitemap8_2026.xml ...) also answer with a dropped
  connection (status 0), so only the shards named by the index are fetched.

Verified 2026-10-25: 2571 unique URLs, every day of the window covered (worst day
2026-10-25 with 23, weekdays 91-116), 16 articles re-fetched across all 8 sections gave
HTTP 200, 2983-11461 chars of text and a page date identical to the listed one (two
were published a day after their path date, i.e. within the 1-day tolerance).

Run: python3 scrapers/custom/emol-com.py   (~90 s)
Writes data/urls_custom/emol-com.tsv, one line URL<TAB>YYYY-MM-DD, no header.
All HTTP goes through politeness/robots/rate-limiting via scrapers/polite_fetch.py.
"""
import datetime
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "scrapers"))

from polite_fetch import fetch  # noqa: E402

START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)

INDEX_URL = "https://www.emol.com/sitemap/sitemapIndex.xml"
OUT_PATH = os.path.join(REPO, "data", "urls_custom", "emol-com.tsv")

LOC_RE = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>", re.I)
LASTMOD_RE = re.compile(r"<lastmod>\s*([^<\s]+)\s*</lastmod>", re.I)
PATH_DATE_RE = re.compile(r"/(\d{4})/(\d{2})/(\d{2})/")


def get(url, tries=2):
    """polite_fetch wrapper: returns text on 200, None otherwise (never raises).

    One retry after a pause: a shard carries ~1000 of our URLs, so losing one to a
    transient connection error would cost a whole section of the window.
    """
    for attempt in range(1, tries + 1):
        try:
            status, text, path = fetch(url)
        except Exception as exc:  # network stack surprises must not kill the run
            print("  ! %s -> exception %s (try %d)" % (url, exc, attempt), file=sys.stderr)
            status, text, path = 0, None, "exception"
        if status == 200 and text:
            return text
        print("  ! %s -> status %s (%s) try %d/%d" % (url, status, path, attempt, tries),
              file=sys.stderr)
        if attempt < tries:
            time.sleep(3 * attempt)
    return None


def httpsify(url):
    url = url.strip()
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("http://"):
        return "https://" + url[len("http://"):]
    return url


def url_date(url, lastmod):
    """Publication date: the /YYYY/MM/DD/ segment of the path, else <lastmod>."""
    m = PATH_DATE_RE.search(url)
    if m:
        try:
            return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    if lastmod:
        m = re.match(r"(\d{4})-(\d{2})-(\d{2})", lastmod)
        if m:
            try:
                return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                pass
    return None


def entries_with_lastmod(xml):
    """Yield (loc, lastmod or '') for each <url> entry (or bare <loc> if unpaired)."""
    for block in re.findall(r"(?is)<url\b.*?</url>", xml):
        locs = LOC_RE.findall(block)
        if not locs:
            continue
        lm = LASTMOD_RE.findall(block)
        yield locs[0], (lm[0] if lm else "")
    # sitemapindex-shaped files: bare <loc> entries
    if "<urlset" not in xml.lower():
        for loc in LOC_RE.findall(xml):
            yield loc, ""


def main():
    years = set(range(min(START.year, END.year), max(START.year, END.year) + 1))

    idx = get(INDEX_URL)
    if not idx:
        print("FATAL: sitemap index unreachable", file=sys.stderr)
        return 1

    shards = []
    for loc in LOC_RE.findall(idx):
        m = re.search(r"_(\d{4})\.xml\b", loc)
        if m and int(m.group(1)) in years:
            shards.append(httpsify(loc))
    # de-duplicate, keep order
    seen_shards, ordered = set(), []
    for s in shards:
        if s not in seen_shards:
            seen_shards.add(s)
            ordered.append(s)
    shards = ordered
    print("sitemap index: %d shard(s) for %s" % (len(shards), sorted(years)))

    found = {}  # url -> date
    for shard in shards:
        xml = get(shard)
        if not xml:
            continue
        n = 0
        for loc, lm in entries_with_lastmod(xml):
            url = httpsify(loc)
            d = url_date(url, lm)
            if d is None or not (START <= d <= END):
                continue
            if url not in found:
                found[url] = d
                n += 1
        print("  %-70s %6d urls in window" % (shard.rsplit("/", 1)[-1], n))

    if not found:
        print("FATAL: no URLs collected", file=sys.stderr)
        return 1

    rows = sorted(found.items(), key=lambda kv: (kv[1], kv[0]))
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        for url, d in rows:
            fh.write("%s\t%s\n" % (url, d.isoformat()))

    per_day = {}
    for _, d in rows:
        per_day[d] = per_day.get(d, 0) + 1
    for d in sorted(per_day):
        print("%s  %4d" % (d.isoformat(), per_day[d]))
    print("total unique URLs: %d -> %s" % (len(rows), OUT_PATH))
    return 0


if __name__ == "__main__":
    sys.exit(main())
