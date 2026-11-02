#!/usr/bin/env python3
"""repubblica.it article URLs 2026-09-25..2026-10-25.
Candidates: (1) monthly sitemaps sitemap-2026-09.xml.gz (reaches 09-30) and sitemap-2026-10.xml.gz (only the last 3 days, 10-23..25);
(2) deep section paging https://www.repubblica.it/<section>/?page=N (N up to ~50) for Oct 1-22.
The article path carries the publication date (/YYYY/MM/DD/); lastmod is only a modification time, so the path date is used.
Filter: every candidate is fetched and kept only if trafilatura finds 200+ characters of text (shorter than 1500 = paywall-truncated, marked at fetch time) and a page date within 1 day of the path
date (paywalled stubs give ~400 chars; city sites bologna./genova. are not kept). Runs ~12 min."""
import json, re, sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
import trafilatura
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scrapers"))
from polite_fetch import fetch
OUT = Path("data/urls_custom/la-repubblica-it.tsv")
FIRST, LAST = "2026-09-25", "2026-10-25"
SECTIONS = ["cronaca", "politica", "esteri", "economia", "sport", "spettacoli", "cultura", "salute", "tecnologia", "ambiente", "motori", "scienze"]
ART = re.compile(r"(?:(?:https?:)?//([a-z0-9.-]+\.repubblica\.it))?(/[a-z0-9_/.-]*?/(\d{4})/(\d{2})/(\d{2})/news/[^/\"'<> ?#]+/?)")
cand = {}

def collect(text):
    for m in ART.finditer(text or ""):
        if m.group(1) and m.group(1) != "www.repubblica.it":
            continue
        d = "-".join(m.group(3, 4, 5))
        if FIRST <= d <= LAST:
            cand.setdefault("https://www.repubblica.it" + m.group(2), d)

for month in ("2026-09", "2026-10"):
    for _ in range(3):
        status, text, _ = fetch(f"https://www.repubblica.it/sitemap-{month}.xml.gz", cache=False)
        if status == 200 and text:
            break
    assert status == 200, f"{month}: {status}"
    collect(text)
print("sitemaps:", len(cand), flush=True)

def section(sec):
    page, fails = 1, 0
    while page <= 120:
        status, text, _ = fetch(f"https://www.repubblica.it/{sec}/?page={page}", cache=False)
        if status == 404 or (status == 200 and not text):
            break
        if status != 200:
            fails += 1
            if fails >= 3:
                break
            continue
        fails = 0
        collect(text)
        page += 1
    print(sec, "pages", page - 1, flush=True)
with ThreadPoolExecutor(6) as ex:
    list(ex.map(section, SECTIONS))
print("candidates:", len(cand), flush=True)

def good(item):
    u, d = item
    for _ in range(2):
        status, html, _ = fetch(u, cache=False)
        if status == 200:
            break
    j = json.loads(trafilatura.extract(html, with_metadata=True, output_format="json") or "{}") if status == 200 else {}
    try:
        near = abs((date.fromisoformat((j.get("date") or "")[:10]) - date.fromisoformat(d)).days) <= 1
    except ValueError:
        near = False
    return near and len(j.get("text", "")) >= 200
items = sorted(cand.items(), key=lambda x: (x[1], x[0]))
with ThreadPoolExecutor(8) as ex:
    keep = [it for it, ok in zip(items, ex.map(good, items)) if ok]
OUT.parent.mkdir(parents=True, exist_ok=True)
tmp = OUT.with_suffix(".tmp")
tmp.write_text("".join(f"{u}\t{d}\n" for u, d in keep))
tmp.replace(OUT)
for d, n in sorted(Counter(d for _, d in keep).items()):
    print(d, n)
print("total", len(keep), "of", len(items), "candidates")
