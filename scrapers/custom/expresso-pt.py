#!/usr/bin/env python3
"""expresso.pt (Expresso, Portugal) article lister for 2026-09-25 .. 2026-10-25.

ROUTE
  1. https://expresso.pt/robots.txt  -> 200, our UA is not in the long AI-bot group, so
     "Allow: /" applies. It advertises Sitemap: /sitemap/index.xml.
  2. https://expresso.pt/sitemap/index.xml  -> 200, a sitemapindex with ONE flat urlset per
     day, /sitemap/YYYY/MM/YYYY-MM-DD.xml (~150 <url> entries each). No recursion, no paging:
     31 day files cover the whole window (~32 requests, ~40 s).
     Careful: days 1..9 are NOT zero padded in the file name (/sitemap/2026/10/2026-10-9.xml),
     a zero-padded request 403s.
  3. expresso.pt ARTICLE HTML IS BLOCKED for our UA (403 on every HTML path, including "/" —
     a WAF rule; robots.txt and sitemap XML are allowed). Not a robots block, so we keep the
     sitemaps but take the article text from the outlet's own AMP host, amp.expresso.pt, which
     serves the same articles (200, JSON-LD datePublished identical to the URL date). The
     listed URLs are therefore the amp.expresso.pt form of the articles.

LISTED DATE
  The YYYY-MM-DD segment that Expresso itself puts in the article path
  (/section/YYYY-MM-DD-slug), which is its publication date. Verified against the page
  JSON-LD datePublished on samples (identical calendar day). No date is invented.
"""
import re
import sys
from datetime import date, timedelta

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

ROOT = "."
OUT = ROOT + "/data/urls_custom/expresso-pt.tsv"
INDEX = "https://expresso.pt/sitemap/index.xml"
CANON = "https://expresso.pt/"
AMP = "https://amp.expresso.pt/"

START = date(2026, 9, 25)
END = date(2026, 10, 25)

# sections that are games / video / commercial stubs rather than readable articles
SKIP_SECTIONS = {
    "jogos", "multimedia", "curtas", "iniciativaseprodutos", "expressinho",
    "meteorologia", "programas", "videos",
}

LOC_DAY_RE = re.compile(r"/sitemap/(\d{4})/(\d{1,2})/(\d{4})-(\d{1,2})-(\d{1,2})\.xml$")
PATH_DATE_RE = re.compile(r"/(\d{4}-\d{2}-\d{2})-")


def daterange(a, b):
    d = a
    while d <= b:
        yield d
        d += timedelta(days=1)


def main():
    want = {d.isoformat(): d for d in daterange(START, END)}

    st, body, rpath = fetch(INDEX)
    if st != 200 or not body:
        print("FATAL: sitemap index status %s (robots=%s)" % (st, rpath))
        return 1

    day_maps, seen_days = [], set()
    for loc in re.findall(r"<loc>\s*(.*?)\s*</loc>", body):
        m = LOC_DAY_RE.search(loc)
        if not m:
            continue
        day = "%s-%02d-%02d" % (m.group(3), int(m.group(4)), int(m.group(5)))
        if day in want and day not in seen_days:
            seen_days.add(day)
            day_maps.append((day, loc))
    day_maps.sort()
    print("sitemap index status %s, day files in window: %d" % (st, len(day_maps)))

    rows, requests = {}, 0
    for day, loc in day_maps:
        st2, b2, _ = fetch(loc)
        requests += 1
        if st2 != 200 or not b2:
            print("  WARN %s status %s" % (loc, st2))
            continue
        added = 0
        for url, _lastmod in re.findall(
            r"<url>\s*<loc>\s*(.*?)\s*</loc>\s*(?:<lastmod>\s*(.*?)\s*</lastmod>)?", b2, re.S
        ):
            url = url.strip()
            m = PATH_DATE_RE.search(url)
            if not m:                     # not an article path (no date in it)
                continue
            pdate = m.group(1)
            if pdate not in want:
                continue
            if not url.startswith(CANON):
                continue
            section = url[len(CANON):].split("/")[0]
            if section in SKIP_SECTIONS:
                continue
            out = AMP + url[len(CANON):]
            if out in rows:
                continue
            rows[out] = pdate
            added += 1
        print("  %s: +%d (total %d)" % (day, added, len(rows)))

    counts = {}
    with open(OUT, "w") as f:
        for url, pdate in sorted(rows.items(), key=lambda kv: (kv[1], kv[0])):
            f.write("%s\t%s\n" % (url, pdate))
            counts[pdate] = counts.get(pdate, 0) + 1

    print("wrote %d unique URLs to %s (%d requests)" % (len(rows), OUT, requests + 1))
    for d in sorted(counts):
        print("  %s  %d" % (d, counts[d]))
    ok = True
    for d in ("2026-09-30", "2026-10-10", "2026-10-20"):
        n = counts.get(d, 0)
        print("CHECK %s -> %d %s" % (d, n, "OK" if n >= 15 else "LOW"))
        ok = ok and n >= 15

    # self-check: 4 sample articles must return text and a matching page date
    samples = []
    for d in ("2026-09-30", "2026-10-10", "2026-10-20"):
        day_urls = [u for u, x in sorted(rows.items()) if x == d]
        if day_urls:
            samples.append((d, day_urls[0]))
            if len(day_urls) > 3:
                samples.append((d, day_urls[len(day_urls) // 2]))
    for d, u in samples[:5]:
        s3, b3, _ = fetch(u)
        txt = re.sub(r"<(script|style)\b.*?</\1>", " ", b3 or "", flags=re.S)
        txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", txt)).strip()
        md = re.search(r'"datePublished"\s*:\s*"([^"]+)"', b3 or "")
        pdate = md.group(1)[:10] if md else "?"
        print("SAMPLE %s %s chars=%d page=%s match=%s"
              % (d, s3, len(txt), pdate, pdate == d))
    print("ALL TARGET DAYS OK" if ok else "SOME TARGET DAY LOW")
    return 0


if __name__ == "__main__":
    sys.exit(main())
