#!/usr/bin/env python3
"""Nezavisne novine (nezavisne.com) -- article URLs 2026-09-25 .. 2026-10-25.

Route that works: category pages paginate with
  ?after_dat=YYYY-MM-DD+HH%3AMM%3ASS&after_id=<id>
and expose the next anchor in <link rel="next">. Arbitrary anchors are accepted,
so a category can be asked straight at a day boundary. A page holds 15 articles,
newest first, all strictly older than after_dat; if the page's own next anchor
still lands on day D then every article on it was published on D. That gives the
publish day without visiting the article (it equals the JSON-LD datePublished).
robots.txt allows "/" for "*"; /news-sitemap.xml covers only ~2 days and
/sitemap.xml is 404, so sitemaps cannot cover a month.
"""
import sys, os, re, html, datetime as dt
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "scrapers"))
from polite_fetch import fetch  # noqa: E402

OUT = os.path.join(ROOT, "data", "urls_custom", "nezavisne-com.tsv")
START = dt.date(2026, 9, 25)
END = dt.date(2026, 10, 25)
TARGET = 34
MAX_REQ = 420

LANES = [
    "novosti/bih", "novosti/svijet", "novosti/hronika", "novosti/drustvo",
    "novosti/banjaluka", "novosti/gradovi", "novosti/obrazovanje",
    "novosti/intervju", "novosti/kolumne", "novosti/ex-yu",
    "sport/fudbal", "sport/kosarka", "sport/tenis", "sport/rukomet",
    "sport/ostali", "sport/atletika", "sport/zimski-sportovi",
    "sport/sportovi-na-vodi",
    "ekonomija/privreda", "ekonomija/trziste", "ekonomija/analize",
    "ekonomija/agrar",
    "magazin/zanimljivosti", "magazin/scena", "magazin/tv", "magazin/jet-set",
    "magazin/horoskop",
    "zivot-stil/zdravlje", "zivot-stil/zivot", "zivot-stil/hrana-pice",
    "zivot-stil/putovanje", "zivot-stil/ljepota", "zivot-stil/kuca-vrt",
    "zivot-stil/recept", "zivot-stil/zivotinje",
    "kultura/film", "kultura/muzika", "kultura/pozornica",
    "kultura/vizuelna-umjetnost", "kultura/knjizevnost",
    "nauka-tehnologija/nauka", "nauka-tehnologija/internet",
    "nauka-tehnologija/svemir", "nauka-tehnologija/gadgets",
    "nauka-tehnologija/hardware", "nauka-tehnologija/programi",
    "nauka-tehnologija/istorija", "nauka-tehnologija/okolina",
    "automobili/auto-novosti", "automobili/recenzije",
]

ART_RE = re.compile(r'href="(//www\.nezavisne\.com/(?:[a-z0-9\-]+/)+[^"?#]*?/(\d{6,}))"')
NEXT_RE = re.compile(r'<link rel="next" href="([^"]+)"')
JP_RE = re.compile(r'datePublished"\s*:\s*"(\d{4}-\d{2}-\d{2})')
REQ = {"n": 0}
def norm(u):
    if u.startswith("//"):
        u = "https:" + u
    return u.split("?")[0].split("#")[0]
def get(url):
    if REQ["n"] >= MAX_REQ:
        return None
    REQ["n"] += 1
    st, t, _p = fetch(url)
    if st != 200 or not t:
        return None
    return t
def page_articles(t):
    seen, out = set(), []
    for m in ART_RE.finditer(t):
        u = norm(m.group(1))
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out
def page_boundary(t):
    m = NEXT_RE.search(t)
    if not m:
        return None
    href = html.unescape(m.group(1)).replace("%3A", ":")
    b = re.search(r"after_dat=(\d{4}-\d{2}-\d{2})[+ ]\d{2}:", href)
    if not b:
        return None
    return dt.date.fromisoformat(b.group(1))
