#!/usr/bin/env python3
"""COPE (Spain) — cope.es — article URLs published 2026-09-25 .. 2026-10-25.

Route: robots.txt is permissive for our UA (only /search/ and /wp-admin/ disallowed;
no Sitemap: line). /sitemap.xml and /sitemap_index.xml are 404, but /sitemap-index.xml
is a 345-entry sitemapindex that names per-month news files
  https://www.cope.es/sitemap-noticias-YYYYMM.xml.gz
Each is a flat <urlset> of article URLs with <lastmod>. On this site <lastmod> IS the
publication stamp: it matched the page's JSON-LD "datePublished" to the second on 4/4
sampled articles (2026-09-30T14:15:00+02:00, 2026-10-10T08:00:00+02:00,
2026-10-20T15:41:15+02:00, 2026-10-05T13:01:45+02:00), so the lastmod date-part is
the listed date. Two month files (202609, 202610) cover the whole window.

Writes data/urls_custom/cope-es.tsv  (URL<TAB>YYYY-MM-DD, no header, unique URLs).
"""
import os
import re
import sys
import collections

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

ROOT = "."
OUT = os.path.join(ROOT, "data/urls_custom/cope-es.tsv")
BASE = "https://www.cope.es"
START, END = "2026-09-25", "2026-10-25"          # inclusive, date-part comparison

LOC_RE = re.compile(r"<loc>\s*(.*?)\s*</loc>\s*<lastmod>\s*(.*?)\s*</lastmod>", re.S)
URL_RE = re.compile(r"<url>(.*?)</url>", re.S)


def months(start, end):
    y, m = int(start[:4]), int(start[5:7])
    ey, em = int(end[:4]), int(end[5:7])
    out = []
    while (y, m) <= (ey, em):
        out.append("%04d%02d" % (y, m))
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def month_sitemaps():
    """Preferred: the news month files named by /sitemap-index.xml.

    Falls back to probing the derived month URLs directly if the index is unusable.
    """
    wanted = set("sitemap-noticias-%s.xml.gz" % mm for mm in months(START, END))
    found, index_status = [], None
    status, body, _ = fetch(BASE + "/sitemap-index.xml")
    index_status = status
    if status == 200 and body:
        for loc in re.findall(r"<loc>\s*(.*?)\s*</loc>", body):
            name = loc.rsplit("/", 1)[-1]
            if name in wanted and loc not in found:
                found.append(loc)
    for mm in months(START, END):
        direct = "%s/sitemap-noticias-%s.xml.gz" % (BASE, mm)
        if direct not in found:
            found.append(direct)
    print("sitemap-index.xml -> %s ; month files: %d" % (index_status, len(found)))
    return found


def main():
    rows = []                                   # (url, date)
    seen = set()
    for sm in month_sitemaps():
        status, body, _ = fetch(sm)
        pairs = LOC_RE.findall(body or "")
        if not pairs:                            # tolerate <url> blocks without lastmod
            pairs = []
            for blk in URL_RE.findall(body or ""):
                m = re.search(r"<loc>\s*(.*?)\s*</loc>", blk, re.S)
                if m:
                    pairs.append((m.group(1), ""))
        kept = 0
        for url, lastmod in pairs:
            url = url.strip()
            day = (lastmod or "").strip()[:10]
            if not day or not (START <= day <= END):
                continue
            if url in seen:
                continue
            seen.add(url)
            rows.append((url, day))
            kept += 1
        print("%s -> HTTP %s, %d entries, %d in window" % (sm.rsplit("/", 1)[-1], status, len(pairs), kept))

    rows.sort(key=lambda r: (r[1], r[0]))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for url, day in rows:
            f.write("%s\t%s\n" % (url, day))
    os.replace(tmp, OUT)

    per_day = collections.Counter(day for _, day in rows)
    print("\nwrote %d URLs to %s" % (len(rows), OUT))
    for day in sorted(per_day):
        print("  %s  %d" % (day, per_day[day]))
    print("  distinct days: %d / %d" % (len(per_day), 31))


if __name__ == "__main__":
    main()
