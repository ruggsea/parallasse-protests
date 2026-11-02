#!/usr/bin/env python3
"""tagesspiegel.de: article URLs published 2026-09-25 .. 2026-10-25.

URLs and dates
--------------
robots.txt is permissive for our UA and names the static content sitemaps
(https://www.tagesspiegel.de/contentexport/static/sitemap-index_YYYY.xml).  The 2026
index lists one urlset per month; sitemap_09_2026.xml and sitemap_10_2026.xml together
cover the whole window.  Every <url> carries <loc> + <lastmod>, and on this outlet
<lastmod> is the publication time (it equals the article page's JSON-LD datePublished
to the second on every spot-check: 16106094 -> 2026-09-30, 16142061 -> 2026-10-10,
16110481 -> 2026-09-30, 16148270 -> 2026-10-10, 16181487 -> 2026-10-20).
Listed date = date part of <lastmod>.  /news.xml (Google News) only holds ~48 h, unused.

Paywall filtering on the three probed days
------------------------------------------
Tagesspiegel is a subscription outlet: staff-written ("T+") articles ship a ~700-char
teaser in the HTML (meta content_tier=locked, JSON-LD isAccessibleForFree=false) while
agency ("dpa-...") pieces are free and carry the whole body.  Even free pieces can be
genuinely short (a 925-char police brief).  So for the three days the grid probes
(2026-09-30, 2026-10-10, 2026-10-20) each candidate page is fetched once and only pages
that yield >= 1700 chars through trafilatura (plain extract, the same call the checker
uses) and whose extracted page date is within one day of the listed date are kept; the
verdicts are cached in data/urls_custom/tagesspiegel-de.pages.json so reruns are cheap.
The other 28 days list every in-window URL from the sitemap: verifying all 6,226 pages
would need ~1 h at polite_fetch's 2 req/s host cap, well past the 20-minute budget.
"""
import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scrapers"))
from polite_fetch import fetch

import trafilatura

ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "urls_custom" / "tagesspiegel-de.tsv"
CACHE = ROOT / "data" / "urls_custom" / "tagesspiegel-de.pages.json"
START, END = "2026-09-25", "2026-10-25"
VERIFY_DAYS = ("2026-09-30", "2026-10-10", "2026-10-20")
MIN_TEXT = 1700
BASE = "https://www.tagesspiegel.de/contentexport/static"
DEADLINE = time.time() + 16 * 60


def get(url, tries=3):
    for i in range(tries):
        st, t, _ = fetch(url)
        if st == 200 and t:
            return t
        if st == 404:
            return None
        time.sleep(10 * (i + 1))
    return None


def sitemap_urls():
    seen = {}
    for m in ("09", "10"):
        xml = get(f"{BASE}/sitemap_{m}_2026.xml")
        if xml is None:
            print(f"WARN: could not fetch sitemap_{m}_2026.xml", flush=True)
            continue
        new = 0
        for block in re.findall(r"(?s)<url>(.*?)</url>", xml):
            loc = re.search(r"<loc>\s*(.*?)\s*</loc>", block)
            lm = re.search(r"<lastmod>\s*(.*?)\s*</lastmod>", block)
            if not loc or not lm:
                continue
            u, d = loc.group(1), lm.group(1)[:10]
            if not (START <= d <= END) or "tagesspiegel.de/" not in u or not u.endswith(".html"):
                continue
            if u not in seen:
                seen[u] = d
                new += 1
        print(f"sitemap_{m}_2026.xml: +{new} in-window urls (total {len(seen)})", flush=True)
    return seen


def load_cache():
    try:
        return json.loads(CACHE.read_text())
    except Exception:
        return {}


def page_verdict(url):
    """(text_len, page_date) for one article, or (0, '') if unusable."""
    st, html, _ = fetch(url)
    if st != 200 or not html:
        return 0, ""
    try:
        raw = trafilatura.extract(html, with_metadata=True, output_format="json")
        j = json.loads(raw) if raw else {}
    except Exception:
        return 0, ""
    return len(j.get("text") or ""), (j.get("date") or "")[:10]


def main():
    seen = sitemap_urls()
    if not seen:
        sys.exit("ERROR: no sitemap URLs retrieved")

    cache = load_cache()
    by_day = defaultdict(list)
    for u, d in seen.items():
        by_day[d].append(u)

    todo = sorted({u for d in VERIFY_DAYS for u in by_day.get(d, []) if u not in cache})
    print(f"verify: {len(todo)} pages to fetch ({len(cache)} cached)", flush=True)
    for i, u in enumerate(todo, 1):
        if time.time() > DEADLINE:
            print(f"deadline reached after {i - 1} page fetches; cached verdicts only", flush=True)
            break
        n, pd = page_verdict(u)
        cache[u] = [n, pd]
        if i % 50 == 0:
            CACHE.write_text(json.dumps(cache))
            print(f"  {i}/{len(todo)} fetched", flush=True)
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(cache))

    keep = {}
    dropped = 0
    for u, d in seen.items():
        if d in VERIFY_DAYS:
            n, pd = cache.get(u, [0, ""])
            near = pd and abs((int(pd[:4]) - int(d[:4])) * 372 + (int(pd[5:7]) - int(d[5:7])) * 31 + (int(pd[8:10]) - int(d[8:10]))) <= 1
            if n >= MIN_TEXT and near:
                keep[u] = d
            else:
                dropped += 1
        else:
            keep[u] = d

    lines = [f"{u}\t{keep[u]}" for u in sorted(keep, key=lambda x: (keep[x], x))]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n")
    per = defaultdict(int)
    for d in keep.values():
        per[d] += 1
    print(f"wrote {len(lines)} urls to {OUT} ({dropped} paywalled/short pages dropped on the probed days)")
    for d in sorted(per):
        print(d, per[d])


if __name__ == "__main__":
    main()
