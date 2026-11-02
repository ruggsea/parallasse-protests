#!/usr/bin/env python3
"""Scraper for GroundUp (South Africa), groundup.org.za.

Window: 2026-09-25 .. 2026-10-25 (inclusive).

Route (verified 2026-10-27, ~20 requests total while probing):
- robots.txt is 200 and permissive: only /admin/, /invoices/, /preview/, /prev_gen/,
  /copy_article/, /article_print/, /commissions/, /newsbypk/ are disallowed. It names
  `Sitemap: https://groundup.org.za/sitemap.xml`.
- That sitemap (200, ~3.7 MB) is ONE flat <urlset> of 20,095 <loc>/<lastmod> pairs,
  newest first, covering the whole archive (oldest lastmod 2012-04-16). <lastmod> is
  DATE-ONLY and IS the publication date here: it equalled the article page's
  article:published_time date on 12/12 checked pages spread over 2026-09-28, 09-30,
  10-09, 10-10, 10-16, 10-20 and 10-23 (e.g. march-and-march lastmod 2026-09-30 ==
  published_time 2026-09-30T17:58+02:00). Only 15 URLs in the whole sitemap have a
  lastmod after the window, all of them articles published on 10-26/10-27, so there is
  no "edited much later" drift to correct for.
- One fetch therefore yields URL + publication date for the whole window.

What does NOT work / is not needed:
- RSS https://groundup.org.za/sitenews/rss/ is 200 but holds only 15 items (~4 days).
- /wp-json/, /feed/, /news-sitemap.xml do not exist (fetch returned no body) - this is a
  Django site, not WordPress.
- The sitemap also lists author profile pages (58 in window) and video pages; only
  /article/ URLs are kept, since they are the pages that carry the article text.

Volume note: this is a small non-profit newsroom. It publishes ~5-7 articles on a weekday
and 0-2 at weekends, so 15 articles on a single day never happens. Counts per required
day from this sitemap: 2026-09-30 = 5 articles, 2026-10-10 (Saturday) = 1,
2026-10-20 = 6. Hence "low_volume": true in the grid JSON; the list is the outlet's whole
output, not a crawl shortfall (115 article URLs in the 31-day window, ~3.7/day).
"""
import os
import re
import sys
from datetime import date

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

START = date(2026, 9, 25)
END = date(2026, 10, 25)
SITEMAP = "https://groundup.org.za/sitemap.xml"
OUT_PATH = "data/urls_custom/groundup-org-za.tsv"

PAIR_RE = re.compile(
    r"<loc>\s*([^<\s]+)\s*</loc>\s*<lastmod>\s*(\d{4}-\d{2}-\d{2})", re.S
)


def load_sitemap():
    """Fetch the sitemap, retrying once. Returns the XML text or None."""
    for attempt in (1, 2, 3):
        try:
            status, text, _ = fetch(SITEMAP)
        except Exception as exc:  # network hiccup: retry
            print(f"sitemap attempt {attempt}: exception {exc}", file=sys.stderr)
            continue
        if status == 200 and text and "<urlset" in text:
            print(f"sitemap: status 200, {len(text)} bytes (attempt {attempt})")
            return text
        print(f"sitemap attempt {attempt}: status {status}", file=sys.stderr)
    return None


def main():
    text = load_sitemap()
    if text is None:
        print("could not fetch the sitemap; nothing written", file=sys.stderr)
        return 1

    pairs = PAIR_RE.findall(text)
    print(f"sitemap entries: {len(pairs)}")

    rows = {}  # url -> date (first occurrence wins; sitemap is newest-first)
    for url, day in pairs:
        if "/article/" not in url:
            continue  # skip author pages, video pages, static pages
        try:
            y, m, d = (int(x) for x in day.split("-"))
            pub = date(y, m, d)
        except ValueError:
            continue
        if START <= pub <= END and url not in rows:
            rows[url] = pub

    ordered = sorted(rows.items(), key=lambda kv: (kv[1], kv[0]))

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        for url, pub in ordered:
            fh.write(f"{url}\t{pub.isoformat()}\n")

    per_day = {}
    for _, pub in ordered:
        per_day[pub] = per_day.get(pub, 0) + 1

    print(f"wrote {len(ordered)} URLs to {OUT_PATH}")
    for pub in sorted(per_day):
        print(f"{pub.isoformat()}\t{per_day[pub]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
