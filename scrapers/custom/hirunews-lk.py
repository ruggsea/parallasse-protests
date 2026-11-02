#!/usr/bin/env python3
"""hirunews.lk (Hiru TV, Sri Lanka) -> article URLs 2026-09-25..2026-10-25.

Route: robots.txt advertises https://www.hirunews.lk/sitemaps/index.php, a flat
<urlset> of chunk files (english-N.xml, sinhala-N.xml, tamil-N.xml, 1000 URLs per
chunk).  Each chunk is a Google-News urlset whose <news:publication_date> IS the
publish date stated by the site and chunks are ordered ASCENDING by that date, so
we binary-search the chunk holding the window start and then walk forward.
"""
import re
import sys
from collections import Counter

sys.path.insert(0, "scrapers")
from polite_fetch import fetch  # noqa: E402

BASE = "https://www.hirunews.lk"
INDEX = BASE + "/sitemaps/index.php"
START, END = "2026-09-25", "2026-10-25"
OUT = "data/urls_custom/hirunews-lk.tsv"

LOC_RE = re.compile(r"<loc>\s*(.*?)\s*</loc>", re.S)
DATE_RE = re.compile(r"<news:publication_date>\s*(\d{4}-\d{2}-\d{2})", re.S)


def get(url, tries=3):
    for i in range(tries):
        try:
            st, txt, _ = fetch(url)
        except Exception:
            st, txt = 0, ""
        if st == 200 and txt:
            return txt
        print("  retry", st, url, file=sys.stderr)
    return ""


def chunk_urls(prefix, n):
    """[(url, date)] for one chunk, [] if the chunk is missing."""
    txt = get(f"{BASE}/sitemaps/{prefix}-{n}.xml")
    if not txt:
        return []
    out = []
    for block in re.findall(r"<url>(.*?)</url>", txt, re.S):
        loc = LOC_RE.search(block)
        dt = DATE_RE.search(block)
        if loc and dt:
            out.append((loc.group(1).strip(), dt.group(1)))
    return out


def chunk_span(prefix, n):
    rows = chunk_urls(prefix, n)
    if not rows:
        return None
    return rows[0][1], rows[-1][1], rows


def main():
    idx = get(INDEX)
    if not idx:
        print("sitemap index unreachable", file=sys.stderr)
        return 1
    chunks = {}
    for lang in ("english", "sinhala", "tamil"):
        ns = sorted({int(x) // 1 for x in re.findall(lang + r"-(\d+)\.xml", idx)})
        if ns:
            chunks[lang] = ns
    print("chunks advertised:", {k: len(v) for k, v in chunks.items()})

    rows = []
    for lang in ("english", "sinhala", "tamil"):
        ns = chunks.get(lang)
        if not ns:
            continue
        # binary search: first chunk whose last date >= START
        lo, hi = 0, len(ns) - 1
        first = None
        while lo <= hi:
            mid = (lo + hi) // 2
            span = chunk_span(lang, ns[mid])
            if span is None:
                hi = mid - 1
                continue
            if span[1] >= START:
                first = mid
                hi = mid - 1
            else:
                lo = mid + 1
        if first is None:
            first = 0
        print(f"{lang}: starting at chunk {ns[first]}")
        i = first
        while i < len(ns):
            span = chunk_span(lang, ns[i])
            i += 1
            if span is None:
                continue
            if span[0] > END:
                break
            rows.extend(span[2])

    seen = set()
    keep = []
    for u, d in rows:
        if not (START <= d <= END):
            continue
        u = u.replace("http://hirunews.lk", "https://hirunews.lk")
        key = u.rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        keep.append((u, d))
    keep.sort(key=lambda r: (r[1], r[0]))

    with open(OUT, "w") as f:
        for u, d in keep:
            f.write(f"{u}\t{d}\n")

    c = Counter(d for _, d in keep)
    print(f"wrote {len(keep)} URLs to {OUT}")
    for d in sorted(c):
        print(f"  {d}\t{c[d]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
