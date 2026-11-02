#!/usr/bin/env python3
"""Scraper for Sábado (sabado.pt, Portugal).

Route (verified 2026-10-26):
  robots.txt -> 404 (assumed open).
  The site exposes a per-DAY Google News sitemap endpoint discovered on the
  homepage: https://www.sabado.pt/sitemap?yyyy=YYYY&mm=MM&dd=DD
  One request per day covers the whole window. Each <url> carries a
  <news:publication_date> (site-local +01:00/+02:00) which is the listed date
  (verified == page JSON-LD datePublished on 8 samples).
  Excluded: /video/detalhe/ (pages have no date) and /newsletter/ (404).

Writes data/urls_custom/sabado-pt.tsv: URL<TAB>YYYY-MM-DD, unique, no header.
All HTTP goes through polite_fetch.
"""
import os
import re
import sys
import datetime as dt
import xml.etree.ElementTree as ET

REPO = "."
sys.path.insert(0, os.path.join(REPO, "scrapers"))
from polite_fetch import fetch  # noqa: E402

START = dt.date(2026, 9, 25)
END = dt.date(2026, 10, 25)
OUT = os.path.join(REPO, "data", "urls_custom", "sabado-pt.tsv")

def parse_date(text):
    if not text:
        return None
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    if not m:
        return None
    try:
        return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None

def main():
    found = {}  # url -> date
    day_counts = {}
    day = START
    while day <= END:
        url = (f"https://www.sabado.pt/sitemap"
               f"?yyyy={day.year}&mm={day.month:02d}&dd={day.day:02d}")
        status, text, _ = fetch(url)
        n = 0
        if status == 200 and text:
            try:
                root = ET.fromstring(text)
            except ET.ParseError:
                root = None
            if root is not None:
                for uel in root.iter():
                    if not uel.tag.endswith("}url") and uel.tag != "url":
                        continue
                    loc = pub = None
                    for child in uel.iter():
                        tag = child.tag
                        if tag == "loc" or tag.endswith("}loc"):
                            if loc is None:
                                loc = (child.text or "").strip()
                        elif tag == "publication_date" or tag.endswith("}publication_date"):
                            if pub is None:
                                pub = (child.text or "").strip()
                    if not loc or not loc.startswith("http"):
                        continue
                    # /video/ pages carry no date at all (VideoObject only), and
                    # /newsletter/ detail URLs 404 (checked 2026-10-26); drop both.
                    path = loc.split("?", 1)[0]
                    if re.search(r"/video/detalhe/", path) or re.search(r"/newsletter/", path):
                        continue
                    d = parse_date(pub)
                    if d is None:
                        continue
                    # dedupe: first date seen for a URL wins (sitemaps are per-day
                    # so re-listed articles keep their original publication date)
                    if loc not in found:
                        found[loc] = d
                        n += 1
        day_counts[day.isoformat()] = n
        print(f"{day.isoformat()}  status={status}  new={n}  total={len(found)}")
        day += dt.timedelta(days=1)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    rows = []
    for u in sorted(found):
        d = found[u]
        if START <= d <= END:
            rows.append((u, d.isoformat()))
    rows.sort(key=lambda r: (r[1], r[0]))
    with open(OUT, "w", encoding="utf-8") as f:
        for u, d in rows:
            f.write(f"{u}\t{d}\n")

    print(f"WROTE {len(rows)} urls -> {OUT}")
    # per-day output counts
    out_counts = {}
    for _, d in rows:
        out_counts[d] = out_counts.get(d, 0) + 1
    for d in sorted(out_counts):
        print(f"out {d}: {out_counts[d]}")

if __name__ == "__main__":
    main()
