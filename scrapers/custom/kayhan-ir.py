#!/usr/bin/env python3
"""kayhan.ir (Kayhan, Iran) article URL lister for 2026-09-25 .. 2026-10-25.

Route: robots.txt Sitemap lines -> https://kayhan.ir/fa-sitemap-newsarchive is a
sitemapindex of per-Persian-month chunks named
  fa-sitemap-newsarchive-<year>-<month>-<chunk>   (e.g. 1405-7-33)
Each chunk is a flat <urlset> of /fa/news/<id>/<slug> with <lastmod>, and
<lastmod> == the page's JSON-LD datePublished to the second (6/6 spot checks),
so the date is the date-part of <lastmod> in site-local time (+03:30).

The index does not list every chunk that the server will still serve, and one
chunk (1405-8-33) is occasionally 500, so we also probe a couple of derived
chunk names. The Google-News sitemap (fa-sitemap-news) is merged in as a
fallback for the most recent days.
"""
import re
import sys
from collections import Counter

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

BASE = "https://kayhan.ir"
INDEX = BASE + "/fa-sitemap-newsarchive"
NEWS = BASE + "/fa-sitemap-news"
OUT = "data/urls_custom/kayhan-ir.tsv"

START, END = "2026-09-25", "2026-10-25"

# My crude strip of a whole kayhan page yields ~1200 chars of nav/footer chrome, so a
# page needs a real body to reach the check's 1500-char bar. Verified near-empty:
# "هدیه به خوانندگان" (daily contest page, <meta article:word_count> = 18, ~40 chars of text).
SKIP_SLUGS = {"%D9%87%D8%AF%DB%8C%D9%87-%D8%A8%D9%87-%D8%AE%D9%88%D8%A7%D9%86%D9%86%D8%AF%DA%AF%D8%A7%D9%86"}  # هدیه-به-خوانندگان

LOC_RE = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>")
URL_LM_RE = re.compile(
    r"<url>\s*<loc>\s*([^<\s]+)\s*</loc>\s*<lastmod>\s*([^<\s]+)\s*</lastmod>", re.S)
NEWS_RE = re.compile(
    r"<loc>\s*([^<\s]+)\s*</loc>.*?<news:publication_date>\s*([^<\s]+)\s*</news:publication_date>", re.S)


def in_window(d):
    return START <= d <= END


def get(url):
    try:
        st, tx, _ = fetch(url)
    except Exception as e:  # noqa: BLE001
        print("  fetch error", url, e, file=sys.stderr)
        return 0, ""
    if st != 200 or not tx:
        print("  status", st, "for", url, file=sys.stderr)
        return st, ""
    return st, tx


def main():
    found = {}  # url -> 'YYYY-MM-DD'

    # 1) sitemap index of news-archive chunks
    st, tx = get(INDEX)
    chunks = []
    if tx:
        for loc in LOC_RE.findall(tx):
            m = re.search(r"-(\d{4})-(\d{1,2})-(\d{1,2})$", loc)
            if m and int(m.group(1)) >= 1405 and (int(m.group(1)) > 1405 or int(m.group(2)) >= 6):
                chunks.append(loc)
    print("chunks listed in index:", len(chunks))

    # 2) also probe derived chunk names the index may omit (gaps/500s)
    extra = [BASE + "/fa-sitemap-newsarchive-1405-8-33",
             BASE + "/fa-sitemap-newsarchive-1405-7-32"]
    for e in extra:
        if e not in chunks:
            chunks.append(e)

    for c in chunks:
        st, tx = get(c)
        if not tx:
            continue
        n = 0
        for url, lm in URL_LM_RE.findall(tx):
            d = lm[:10]
            if in_window(d) and url.rsplit("/", 1)[-1] not in SKIP_SLUGS:
                found[url] = d
                n += 1
        print("  %-60s %5d in-window" % (c.rsplit("/", 1)[-1], n))

    # 3) Google-News sitemap as a top-up (real <news:publication_date>)
    st, tx = get(NEWS)
    if tx:
        n = 0
        for url, pd in NEWS_RE.findall(tx):
            d = pd[:10]
            if in_window(d) and url.rsplit("/", 1)[-1] not in SKIP_SLUGS:
                found.setdefault(url, d)
                n += 1
        print("  %-60s %5d in-window" % ("fa-sitemap-news", n))

    rows = sorted(found.items())
    with open(OUT, "w", encoding="utf-8") as f:
        for url, d in rows:
            f.write("%s\t%s\n" % (url, d))

    per_day = Counter(d for _, d in rows)
    print("wrote %d unique urls to %s" % (len(rows), OUT))
    for d in ("2026-09-30", "2026-10-10", "2026-10-20"):
        print("  target day %s: %d" % (d, per_day.get(d, 0)))
    print("per-day counts:")
    for d in sorted(per_day):
        print("  %s %d" % (d, per_day[d]))


if __name__ == "__main__":
    main()
