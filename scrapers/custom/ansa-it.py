#!/usr/bin/env python3
"""ansa.it article URLs 2026-09-25..2026-10-25; the date is the /YYYY/MM/DD/ in the article path (= page date).
Routes, merged: (1) the 63 per-section sitemaps in sito_sitemap_index.xml (last ~2 days each);
(2) index pages: the home /sito/, each section directory's <dir>/<last>.shtml, and the root page of every channel/region (/<region>/, /canale_<x>/, /europa/):
    these list 1-3 weeks of items (checked: 18-70 articles for Oct 20 on a single region page);
(3) Wayback CDX month-prefix queries web.archive.org/cdx/search/cdx?url=www.ansa.it/<dir>/2026/<MM>/* for the main section directories
    (captures lag ~8 days, so this fills Sep 25-Oct 17).
All requests go through polite_fetch.fetch (robots, per-host rate); the CDX timeout is raised to 120 s. Runs ~10 min."""
import re, sys, time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scrapers"))
import polite_fetch as pf
from polite_fetch import fetch
_orig = pf._get
pf._get = lambda url, timeout=120: _orig(url, 120)
OUT = Path("data/urls_custom/ansa-it.tsv")
ART = re.compile(r"(?:https?://(?:www\.)?ansa\.it)?(/(?:sito|canale_[a-z]+|[a-z]+)/notizie/(?:[a-z0-9_]+/)*?)(\d{4})/(\d{2})/(\d{2})/([^/\s\"'<>?#&]+\.html)")
urls, dirs = {}, set()

def harvest(text):
    for m in ART.finditer(text or ""):
        d = f"{m.group(2)}-{m.group(3)}-{m.group(4)}"
        if "2026-09-25" <= d <= "2026-10-25":
            urls["https://www.ansa.it" + m.group(1) + "/".join(m.group(2, 3, 4, 5))] = d
            dirs.add(m.group(1))

def get(u):
    return fetch(u, cache=False)[1] or ""

status, text, _ = fetch("https://www.ansa.it/sito/sitemaps/sito_sitemap_index.xml", cache=False)
sitemaps = re.findall(r"<loc>([^<]+)</loc>", text or "")
assert sitemaps, f"no sitemap index ({status})"
for sm in sitemaps:
    harvest(get(sm))
print("sitemaps:", len(urls), "urls,", len(dirs), "dirs", flush=True)

indexes = {"https://www.ansa.it/sito/"}
for _ in range(2):  # second pass: directories first seen on index pages
    for d in dirs:
        indexes.add(f"https://www.ansa.it{d}{d.rstrip('/').split('/')[-1]}.shtml")
        if not d.startswith("/sito/"):
            indexes.add(f"https://www.ansa.it/{d.split('/')[1]}/")
    todo = sorted(indexes)
    with ThreadPoolExecutor(4) as ex:
        for t in ex.map(get, todo):
            harvest(t)
    print("index pages:", len(todo), "->", len(urls), "urls", flush=True)

MAIN = ["/sito/notizie/cronaca/", "/sito/notizie/politica/", "/sito/notizie/economia/", "/sito/notizie/mondo/", "/sito/notizie/sport/",
        "/sito/notizie/sport/calcio/", "/sito/notizie/cultura/", "/sito/notizie/tecnologia/", "/sito/notizie/topnews/", "/sito/notizie/mondo/europa/"]
def cdx(args):
    d, month = args
    q = f"https://web.archive.org/cdx/search/cdx?url=www.ansa.it{d}2026/{month}/*&output=txt&fl=original&collapse=urlkey&filter=statuscode:200&limit=30000"
    for attempt in range(3):
        status, text, _ = fetch(q, cache=False)
        if status == 200:
            return text
        time.sleep(15 * (attempt + 1))
    print("CDX failed", d, month, status, file=sys.stderr)
    return ""
with ThreadPoolExecutor(4) as ex:
    for t in ex.map(cdx, [(d, m) for d in MAIN for m in ("09", "10")]):
        harvest(re.sub(r"^http://", "https://", t, flags=re.M))
print("after wayback:", len(urls), flush=True)
OUT.parent.mkdir(parents=True, exist_ok=True)
tmp = OUT.with_suffix(".tmp")
tmp.write_text("".join(f"{u}\t{d}\n" for u, d in sorted(urls.items(), key=lambda x: (x[1], x[0]))))
tmp.replace(OUT)
for d, n in sorted(Counter(urls.values()).items()):
    print(d, n)
print("total", len(urls))
