#!/usr/bin/env python3
"""discover.py ID... : run the verified recipe grids/recipes/out/<ID>.json for every day 2026-09-25..2026-10-25 and write
data/urls/<domain>.tsv (url, listed_date, template). Idempotent (overwrites its own output). Fetching goes through polite_fetch."""
import json, re, sys, urllib.parse, datetime as dt
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from polite_fetch import fetch
R = Path(__file__).resolve().parent.parent
D0, D1 = dt.date(2026, 9, 25), dt.date(2026, 10, 25)
def links(u, text):
    """(url, lastmod_date or None) from a sitemap or an html page"""
    out = []
    for m in re.finditer(r"<url>(.*?)</url>", text, re.S):
        loc = re.search(r"<loc>\s*([^<\s]+)", m.group(1)); lm = re.search(r"<lastmod>\s*(\d{4}-\d\d-\d\d)", m.group(1))
        if loc: out.append((loc.group(1).replace("&amp;", "&"), lm.group(1) if lm else None))
    if out: return out
    return [(urllib.parse.urljoin(u, l.replace("&amp;", "&")), None) for l in re.findall(r"""href=["']([^"'#\s]+)""", text) + re.findall(r"<loc>\s*([^<\s]+)", text)]
def run(cid):
    rec = json.load(open(R/f"grids/recipes/out/{cid}.json"))
    domain = cid.rsplit("-", 1)[0].replace("-", ".") if False else None
    if not rec["list_templates"]: return cid, 0, "no recipe: " + rec["notes"][:100]
    rx = re.compile(rec["article_regex"]); rows = {}; seen = set(); fails = 0
    d = D0
    while d <= D1:
        for t in rec["list_templates"]:
            u = t.replace("{YYYY}", f"{d:%Y}").replace("{MM}", f"{d:%m}").replace("{DD}", f"{d:%d}")
            if u in seen: continue
            seen.add(u)
            st, text, _ = fetch(u)
            if st != 200 or not text: fails += 1; continue
            daily = "{DD}" in t
            for l, lm in links(u, text):
                if not rx.search(l): continue
                day = lm if lm else (f"{d:%Y-%m-%d}" if daily else "")
                if day and not (D0.isoformat() <= day <= D1.isoformat()): continue
                rows.setdefault(l, (day, t))
        d += dt.timedelta(days=1)
    host = urllib.parse.urlparse(next(iter(rows), "http://x/")).netloc
    (R/"data/urls").mkdir(parents=True, exist_ok=True)
    (R/f"data/urls/{cid}.tsv").write_text("url\tlisted_date\ttemplate\n" + "".join(f"{u}\t{v[0]}\t{v[1]}\n" for u, v in rows.items()))
    return cid, len(rows), f"{fails} list pages failed"
if __name__ == "__main__":
    for c in sys.argv[1:]: print(*run(c), flush=True)
