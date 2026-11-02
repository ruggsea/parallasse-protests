#!/usr/bin/env python3
"""corriere.it article URLs 2026-09-25..2026-10-25.
Routes: (1) daily item sitemaps /rss/sitemaps/YYYY/sitemap_MM_DD_items.xml (few items a day);
(2) /dynamic-sitemap/sitemap-last-100/<Section>.xml (newest 100 per section, ~3 days);
(3) the homepage and every section/sub-section page it links (up to 3 path levels, then the section pages those link, 2 rounds):
    slow sections list articles from the whole month, so together they reach back to Sep 1 (checked: 20-120 articles per day);
(Wayback CDX was tried: it only reaches Oct 17 and adds ~1300 URLs at 14 min cost, so it is not used.)
The listed date is the one in the article path (26_ottobre_10 = 2026-10-10), never a capture date.
Filter: each candidate is fetched; kept only if trafilatura finds 200+ chars (headline+lead; articles under 1500 chars are paywall-truncated and marked at fetch time) and a page date within 1 day of the path date."""
import json, re, sys, time, datetime as dt
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import trafilatura
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scrapers"))
from polite_fetch import fetch
OUT = Path("data/urls_custom/corriere-it.tsv")
MONTH = {"settembre": 9, "ottobre": 10}
FIRST, LAST = dt.date(2026, 9, 25), dt.date(2026, 10, 25)
ART = re.compile(r"(?:https?://www\.corriere\.it)?(/[a-z0-9-]+(?:/[a-z0-9-]+)*/26_(settembre|ottobre)_(\d\d)/[^/?#\s\"'<>]+\.shtml)(?![\w])")
DIR = re.compile(r"""href=["'](?:https://www\.corriere\.it)?(/[a-z0-9-]+(?:/[a-z0-9-]+){0,2}/)["']""")
cand = {}

def collect(text):
    for m in ART.finditer(text or ""):
        if "_amp" in m.group(1):
            continue
        d = dt.date(2026, MONTH[m.group(2)], int(m.group(3)))
        if FIRST <= d <= LAST:
            cand["https://www.corriere.it" + m.group(1)] = d.isoformat()

def get(url):
    return fetch(url, cache=False)[1] or ""

for n in range((LAST - FIRST).days + 1):
    d = FIRST + dt.timedelta(n)
    collect("\n".join(re.findall(r"<loc>([^<]+)</loc>", get(f"https://www.corriere.it/rss/sitemaps/{d.year}/sitemap_{d.month:02d}_{d.day:02d}_items.xml"))))
for sec in ["Interni", "Esteri", "Economia", "Sport", "Politica", "Spettacoli", "Cultura", "Salute", "Scienze", "Tecnologia", "Scuola", "Opinioni", "Animali", "Motori", "Moda"]:
    collect("\n".join(re.findall(r"<loc>([^<]+)</loc>", get(f"https://www.corriere.it/dynamic-sitemap/sitemap-last-100/{sec}.xml"))))
print("sitemaps:", len(cand), flush=True)

seen_dirs, frontier = set(), {"/"}
for rnd in range(3):
    batch = sorted(frontier - seen_dirs)[:500]
    seen_dirs |= set(batch)
    def page(d):
        t = get("https://www.corriere.it" + d)
        collect(t)
        return {x for x in DIR.findall(t) if not x.startswith(("/rss", "/dynamic", "/static", "/cook", "/oroscopo"))}
    with ThreadPoolExecutor(6) as ex:
        frontier = set().union(*ex.map(page, batch)) if batch else set()
    print(f"round {rnd}: {len(batch)} pages, candidates {len(cand)}", flush=True)

def good(item):
    u, d = item
    status, html = 0, ""
    for _ in range(2):
        status, html, _ = fetch(u, cache=False)
        if status == 200:
            break
    j = json.loads(trafilatura.extract(html, with_metadata=True, output_format="json") or "{}") if status == 200 else {}
    try:
        near = abs((dt.date.fromisoformat((j.get("date") or "")[:10]) - dt.date.fromisoformat(d)).days) <= 1
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
