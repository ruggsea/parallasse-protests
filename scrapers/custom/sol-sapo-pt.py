#!/usr/bin/env python3
"""Sol (Nascer do Sol, sol.sapo.pt) custom URL scraper, window 2026-09-25..2026-10-25.

Route (verified 2026-10-26):
  robots.txt of sol.sapo.pt (200, permissive for our UA; blocks only AI crawlers)
  -> Sitemap lines point to sol.iol.pt/sitemaps/index.xml (same site, same content:
     same articles served on sol.iol.pt and sol.sapo.pt, identical JSON-LD).
  index.xml lists item_1..N.xml urlsets, newest first, ~1000 entries each, contiguous:
     item_1: 2026-09-30T16:05+01 -> 2026-10-25T23:29Z
     item_2: 2026-09-03T15:36+01 -> 2026-09-30T16:01+01
  The sitemap <lastmod> equals the page dateModified (edit time), NOT datePublished.
  The URL path carries the publication date /YYYYMMDD/ (e.g. .../20260930/...),
  verified == page JSON-LD datePublished on samples. So listed date = path date,
  with lastmod as fallback only for URLs without a path date.

Output: data/urls_custom/sol-sapo-pt.tsv  ->  URL<TAB>YYYY-MM-DD, unique, in-window.
"""
import re
import sys
from collections import Counter
from datetime import date, datetime

sys.path.insert(0, "scrapers")
from polite_fetch import fetch

ROOT = "."
OUT = f"{ROOT}/data/urls_custom/sol-sapo-pt.tsv"
IDX = "https://sol.iol.pt/sitemaps/index.xml"
WIN_START = date(2026, 9, 25)
WIN_END = date(2026, 10, 25)
PATH_DATE = re.compile(r"/(\d{4})(\d{2})(\d{2})/")


def parse_ts(s):
    s = s.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def main():
    status, text, _ = fetch(IDX)
    if status != 200 or not text:
        print(f"FAIL: sitemap index {IDX} -> {status}")
        sys.exit(1)
    subs = []
    for loc, lm in re.findall(r"<sitemap>\s*<loc\s*>(.*?)</loc>\s*(?:<lastmod\s*>(.*?)</lastmod>)?", text, re.S):
        subs.append((loc.strip(), (lm or "").strip()))
    print(f"index: {len(subs)} sub-sitemaps")

    entries = {}  # url -> lastmod_str
    for sm, idx_lm in subs:
        # index lists newest-first; skip sitemaps entirely before the window
        dt = parse_ts(idx_lm)
        if dt and dt.date() < WIN_START:
            print(f"  {sm}: skipped (index lastmod {idx_lm})")
            continue
        st, body, _ = fetch(sm)
        if st != 200 or not body:
            print(f"  WARN: {sm} -> {st}, skipping")
            continue
        blocks = re.findall(r"<url>.*?</url>", body, re.S)
        inwin = 0
        newest = None
        for b in blocks:
            mloc = re.search(r"<loc\s*>(.*?)</loc>", b, re.S)
            if not mloc:
                continue
            loc = mloc.group(1).strip()
            mlm = re.search(r"<lastmod\s*>(.*?)</lastmod>", b, re.S)
            lm = mlm.group(1).strip() if mlm else ""
            dt = parse_ts(lm)
            if dt:
                d = dt.date()
                if newest is None or d > newest:
                    newest = d
            pm = PATH_DATE.search(loc)
            if pm:
                d = date(int(pm.group(1)), int(pm.group(2)), int(pm.group(3)))
            elif dt:
                d = dt.date()
            else:
                continue
            if WIN_START <= d <= WIN_END:
                if loc not in entries:
                    entries[loc] = lm
                inwin += 1
        print(f"  {sm}: {len(blocks)} urls, in-window {inwin}, newest {newest}")
        # sitemaps are newest-first: stop once this one is entirely before the window
        if newest is not None and newest < WIN_START:
            print("  reached pre-window sitemap, stopping")
            break

    # sort: newest URL date first, stable by first-seen order
    dated = []
    for url, lm in entries.items():
        pm = PATH_DATE.search(url)
        if pm:
            d = date(int(pm.group(1)), int(pm.group(2)), int(pm.group(3)))
        else:
            dt = parse_ts(lm)
            d = dt.date() if dt else None
        if d is None:
            continue
        dated.append((d, url))
    dated.sort(key=lambda t: t[0], reverse=True)

    import os
    os.makedirs(f"{ROOT}/data/urls_custom", exist_ok=True)
    seen = set()
    counts = Counter()
    with open(OUT, "w") as f:
        for d, url in dated:
            if url in seen:
                continue
            seen.add(url)
            f.write(f"{url}\t{d.isoformat()}\n")
            counts[d] += 1

    print(f"wrote {len(seen)} URLs to {OUT}")
    for d in sorted(counts):
        print(f"  {d}: {counts[d]}")
    for probe in (date(2026, 9, 30), date(2026, 10, 10), date(2026, 10, 20)):
        print(f"probe {probe}: {counts.get(probe, 0)} (need >= 15)")


if __name__ == "__main__":
    main()
