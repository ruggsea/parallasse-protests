#!/usr/bin/env python3
"""check_countries.py PART START ID  -> prints nothing, exit 0 = accept. Each country row needs 2 fetched (status 200, cached) URLs
on different hosts, a quote that occurs in the cached page, and a pub date in 2026-09-25..2026-10-25. NONE rows need >=4 requests in the fetch log since START."""
import csv, json, sys, re, hashlib, urllib.parse
from pathlib import Path
R = __import__("pathlib").Path(__file__).resolve().parents[2]
part, start, cid = sys.argv[1:4]
norm = lambda t: re.sub(r"\W+", " ", t).lower().strip()
bad = []
rows = list(csv.DictReader(open(part), delimiter="\t"))
need = "country topic start_date scale url1 date1 quote1 url2 date2 quote2".split()
if not rows: bad.append("empty file")
if rows and any(c not in rows[0] for c in need): bad.append("header must be: " + " ".join(need)); rows = []
for r in rows:
    if r["country"] == "NONE":
        n = sum(1 for l in open(R/"logs/fetch.log") if l.split("\t")[0] >= start)
        if n < 4: bad.append(f"NONE row but only {n} requests logged since start (probe at least 4 sources, name them in topic)")
        continue
    hosts = set()
    for k in ("1", "2"):
        u, d, q = r["url"+k], r["date"+k], r["quote"+k]
        f = R/"data/fetchcache"/(hashlib.sha256(u.encode()).hexdigest()[:24]+".json")
        if not f.exists(): bad.append(f"{r['country']}: {u} was not fetched with scrapers/polite_fetch.py"); continue
        j = json.load(open(f))
        if j["status"] != 200: bad.append(f"{r['country']}: {u} status {j['status']}"); continue
        if len(norm(q)) < 25 or norm(q) not in norm(j["text"] or ""): bad.append(f"{r['country']}: quote {k} (>=25 chars, copied exactly) not found in {u}")
        if not ("2026-09-25" <= d <= "2026-10-25"): bad.append(f"{r['country']}: date{k} {d} outside 2026-09-25..2026-10-25")
        hosts.add(urllib.parse.urlparse(u).netloc.removeprefix("www."))
    if len(hosts) < 2: bad.append(f"{r['country']}: the two URLs need different hosts")
print("\n".join(bad)); sys.exit(1 if bad else 0)
