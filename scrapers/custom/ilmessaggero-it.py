#!/usr/bin/env python3
"""Il Messaggero (ilmessaggero.it) article list for 2026-09-25 .. 2026-10-25.

Route: the site advertises a news sitemap via robots.txt:
    https://www.ilmessaggero.it/?sez=XML&p=MapNews
Each <url> element contains <loc>, <lastmod> and a <news:news> block with
<news:publication_date>. Those dates are the authoritative publication dates.
The sitemap only holds recent items, so we supplement with the Wayback CDX API
(https://web.archive.org/cdx/search/cdx) which returns captured URLs. The capture
timestamp is used as a fallback date (the "archive page" date) when the sitemap
does not cover the whole window.

The script writes a TSV file data/urls_custom/ilmessaggero-it.tsv with
"URL\tYYYY-MM-DD" lines (no header), one per unique article, sorted by date.
It prints per‑day counts at the end.
"""
import os
import re
import sys
import time
import json
from datetime import datetime, timedelta

ROOT = str(__import__("pathlib").Path(__file__).resolve().parents[2])
OUT_TSV = os.path.join(ROOT, "data/urls_custom/ilmessaggero-it.tsv")
START = "2026-09-25"
END = "2026-10-25"
BASE_SITEMAP = "https://www.ilmessaggero.it/?sez=XML&p=MapNews"
WAYBACK_CDX = (
    "https://web.archive.org/cdx/search/cdx?url=www.ilmessaggero.it/*"
    "&from=20260925&to=20261025&output=json&collapse=urlkey"
)

# add project scrapers dir to import path for polite_fetch
sys.path.insert(0, os.path.join(ROOT, "scrapers"))
from polite_fetch import fetch  # noqa: E402

def parse_sitemap(xml_text):
    """Extract (url, date) pairs from the sitemap XML.
    Prefer <news:publication_date> if present, otherwise <lastmod>.
    """
    url_re = re.compile(r"<loc>([^<]+)</loc>")
    pubdate_re = re.compile(r"<news:publication_date>([^<]+)T")
    lastmod_re = re.compile(r"<lastmod>([^<]+)T")
    entries = []
    for block in xml_text.split("<url>")[1:]:
        loc_match = url_re.search(block)
        if not loc_match:
            continue
        url = loc_match.group(1).strip()
        date_match = pubdate_re.search(block)
        if date_match:
            date_str = date_match.group(1)[:10]
        else:
            lm_match = lastmod_re.search(block)
            if not lm_match:
                continue
            date_str = lm_match.group(1)[:10]
        entries.append((url, date_str))
    return entries

def fetch_sitemap():
    status, body, _ = fetch(BASE_SITEMAP)
    if status != 200 or not body:
        print(f"Sitemap fetch failed status={status}", flush=True)
        return []
    return parse_sitemap(body)

def fetch_wayback():
    status, body, _ = fetch(WAYBACK_CDX)
    if status != 200 or not body:
        print(f"Wayback CDX fetch failed status={status}", flush=True)
        return []
    try:
        data = json.loads(body)
    except Exception as exc:
        print(f"Wayback JSON decode error: {exc}", flush=True)
        return []
    # first row is header, format: ["urlkey","timestamp","original",...]
    entries = []
    for row in data[1:]:
        try:
            original = row[2]
            ts = row[1]  # YYYYMMDDhhmmss
            date_str = f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"
            entries.append((original, date_str))
        except Exception:
            continue
    return entries

def in_window(date_str):
    return START <= date_str <= END

def main():
    t0 = time.time()
    found = {}  # url -> date
    # 1. sitemap (authoritative dates)
    for url, d in fetch_sitemap():
        if not in_window(d):
            continue
        if url not in found:
            found[url] = d
    # 2. Wayback fallback for missing days
    for url, d in fetch_wayback():
        if not in_window(d):
            continue
        if url not in found:
            found[url] = d
    # write TSV
    os.makedirs(os.path.dirname(OUT_TSV), exist_ok=True)
    tmp = OUT_TSV + ".tmp"
    with open(tmp, "w") as f:
        for u, d in sorted(found.items(), key=lambda kv: (kv[1], kv[0])):
            f.write(f"{u}\t{d}\n")
    os.replace(tmp, OUT_TSV)
    # per‑day counts
    counts = {}
    for d in found.values():
        counts[d] = counts.get(d, 0) + 1
    print(f"wrote {len(found)} unique URLs to {OUT_TSV}")
    print("per day:")
    for d in sorted(counts):
        print(f"  {d}\t{counts[d]}")
    print(f"elapsed {int(time.time() - t0)}s")

if __name__ == "__main__":
    main()
