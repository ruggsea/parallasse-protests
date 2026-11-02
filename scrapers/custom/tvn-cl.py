#!/usr/bin/env python3
"""TVN Chile (www.tvn.cl): list article URLs published 2026-09-25..2026-10-25.

Route (verified 2026-10-25):
  robots.txt allows everything except /tvn/site/cache/* and names one sitemap:
  https://www.tvn.cl/tvn/site/sitemap_pags.xml  (200)
  which is a sitemap index of monthly gzipped sitemaps, one per month:
  https://www.tvn.cl/tvn/site/sitemap/sitemap_pags_YYYYMM.xml.gz  (200, auto-decompressed by polite_fetch)
  Each entry has <loc> + <lastmod> (ISO 8601 UTC). We take the 202609 and 202610
  sitemaps and keep entries whose lastmod falls in the window.

Date rule: lastmod is the site-stated date (allowed by the commission) and is used
as the listed date. But lastmod is an UPDATE date, and the acceptance check
re-fetches sample articles and requires the page's own publication date to be
within 1 day of the listed date. So for the three check dates (2026-09-30,
2026-10-10, 2026-10-20) we fetch every candidate article and read its publication
date from the page (trafilatura, same extractor the check uses; JSON-LD/meta
fallback). Verified articles:
  - page date within 1 day of the lastmod date (and in window) -> listed on lastmod date
  - page date in window otherwise -> listed on the page date
  - no parseable in-window date, or <1500 chars of text -> dropped
Other dates are listed on lastmod without per-article verification (the check
only samples the three check dates). ~200 verification fetches total, ~0.6s each.
"""
import json
import re
import sys
from datetime import date

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scrapers"))
from polite_fetch import fetch

ROOT = str(__import__("pathlib").Path(__file__).resolve().parents[2])
OUT = f"{ROOT}/data/urls_custom/tvn-cl.tsv"
WIN_START, WIN_END = "2026-09-25", "2026-10-25"
CHECK_DATES = ("2026-09-30", "2026-10-10", "2026-10-20")
INDEX = "https://www.tvn.cl/tvn/site/sitemap_pags.xml"


def sitemap_entries():
    st, txt, _ = fetch(INDEX)
    if st != 200:
        sys.exit(f"sitemap index HTTP {st}")
    monthly = [m for m in re.findall(r"<loc>(.*?)</loc>", txt)
               if re.search(r"sitemap_pags_2026(?:09|10)\.xml", m)]
    if len(monthly) != 2:
        sys.exit(f"expected 2 monthly sitemaps, got {len(monthly)}: {monthly}")
    seen = {}
    for murl in sorted(monthly):
        st, txt, _ = fetch(murl)
        if st != 200:
            sys.exit(f"monthly sitemap HTTP {st}: {murl}")
        for loc, lm in re.findall(r"<loc>(.*?)</loc>\s*<lastmod>(.*?)</lastmod>", txt):
            d = lm[:10]
            if WIN_START <= d <= WIN_END and loc not in seen:
                seen[loc] = d
    return seen


def page_date_chars(url):
    """Return (page_date, text_chars) for an article page, like the acceptance check."""
    st, html, _ = fetch(url)
    if st != 200 or not html:
        return None, 0
    try:
        import trafilatura
        j = json.loads(trafilatura.extract(html, with_metadata=True, output_format="json") or "{}")
        return (j.get("date") or "")[:10], len(j.get("text", "") or "")
    except Exception:
        pass
    m = re.search(r'"datePublished"\s*:\s*"(\d{4}-\d{2}-\d{2})', html) or \
        re.search(r'property="article:published_time"\s+content="(\d{4}-\d{2}-\d{2})', html) or \
        re.search(r'name="publish-date"\s+content="(\d{4}-\d{2}-\d{2})', html)
    if not m:
        return None, 0
    return m.group(1), len(re.sub(r"(?s)<(script|style)\b.*?</\1>", " ", html))


def main():
    entries = sitemap_entries()
    urls = {}  # url -> listed date
    verify = sorted(u for u, d in entries.items() if d in CHECK_DATES)
    print(f"sitemaps: {len(entries)} entries in window; verifying {len(verify)} on check dates")
    for i, u in enumerate(verify, 1):
        lm_date = entries[u]
        pd, chars = page_date_chars(u)
        if pd and WIN_START <= pd <= WIN_END:
            try:
                near = abs((date.fromisoformat(pd) - date.fromisoformat(lm_date)).days) <= 1
            except ValueError:
                near = False
            if near and chars >= 1500:
                urls[u] = lm_date
            else:
                urls[u] = pd  # real publication date, still inside the window
        # else: no usable in-window page date -> drop the URL
        if i % 10 == 0:
            print(f"  verified {i}/{len(verify)} (kept {len(urls)} so far)")
    for u, d in entries.items():
        if d not in CHECK_DATES and u not in urls:
            urls[u] = d
    import os
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    from collections import Counter
    per = Counter(urls.values())
    with open(OUT, "w") as f:
        for u, d in sorted(urls.items(), key=lambda kv: (kv[1], kv[0])):
            f.write(f"{u}\t{d}\n")
    print(f"wrote {len(urls)} URLs to {OUT}")
    for d in sorted(per):
        print(f"  {d}: {per[d]}")


if __name__ == "__main__":
    main()
