#!/usr/bin/env python3
"""laverita.info: Yoast post sitemaps. Chunks whose index lastmod >= 2026-09-25 are read (post-sitemap67/68);
chunk entries are in chronological order with lastmod = publication time. Writes data/urls_custom/laverita-info.tsv."""
import collections, os, re, sys
ROOT = str(__import__("pathlib").Path(__file__).resolve().parents[2])
sys.path.insert(0, ROOT + "/scrapers")
from polite_fetch import fetch
OUT = ROOT + "/data/urls_custom/laverita-info.tsv"
S, E = "2026-09-25", "2026-10-25"
st, idx, _ = fetch("https://www.laverita.info/sitemap_index.xml")
chunks = [u for u, d in re.findall(r"<loc>([^<]+)</loc>\s*<lastmod>([^<]+)", idx or "")
          if re.search(r"/post-sitemap\d*\.xml$", u) and d[:10] >= S]
rows = {}
for c in chunks:
    st, t, _ = fetch(c)
    for u, d in re.findall(r"<loc>([^<]+)</loc>\s*<lastmod>([^<]+)", t or ""):
        if S <= d[:10] <= E: rows.setdefault(u, d[:10])
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT + ".tmp", "w") as f:
    for u, d in sorted(rows.items(), key=lambda x: x[1]): f.write(f"{u}\t{d}\n")
os.replace(OUT + ".tmp", OUT)
for d, n in sorted(collections.Counter(rows.values()).items()): print(d, n)
print("total", len(rows), "chunks", chunks)
