#!/usr/bin/env python3
"""check_outlets.py PART ID  -> nothing + exit 0 = accept. Each row: outlet name, domain, kind, evidence url (fetched through polite_fetch, status 200)
and a quote (>=20 chars, copied exactly) that contains the outlet name and occurs in the page. >=5 rows unless the cell says few."""
import csv, json, sys, re, hashlib
from pathlib import Path
R = __import__("pathlib").Path(__file__).resolve().parents[2]
part, cid = sys.argv[1:3]
norm = lambda t: re.sub(r"\W+", " ", t).lower().strip()
need = "outlet domain kind url quote".split()
KINDS = "national_daily regional_daily tv wire online_only magazine public_broadcaster radio weekly".split()
bad = []; rows = list(csv.DictReader(open(part), delimiter="\t"))
if not rows or any(c not in rows[0] for c in need): bad.append("header must be: " + " ".join(need)); rows = []
if rows and len(rows) < 5: bad.append(f"only {len(rows)} outlets; this source should yield at least 5 (search more of it, other pages/tables)")
seen = set()
for r in rows:
    if r["kind"] not in KINDS: bad.append(f"{r['outlet']}: kind must be one of {KINDS}")
    if not re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,}", r["domain"]): bad.append(f"{r['outlet']}: domain must be a bare hostname like repubblica.it")
    if r["domain"] in seen: bad.append(f"duplicate domain {r['domain']}")
    seen.add(r["domain"])
    f = R/"data/fetchcache"/(hashlib.sha256(r["url"].encode()).hexdigest()[:24]+".json")
    if not f.exists(): bad.append(f"{r['outlet']}: {r['url']} not fetched with polite_fetch.py"); continue
    j = json.load(open(f))
    if j["status"] != 200: bad.append(f"{r['outlet']}: {r['url']} status {j['status']}"); continue
    q = norm(r["quote"])
    if len(q) < 20 or q not in norm(j["text"] or ""): bad.append(f"{r['outlet']}: quote not found verbatim in {r['url']}")
    elif norm(r["outlet"]) not in q and norm(r["domain"].split(".")[0]) not in q: bad.append(f"{r['outlet']}: quote must contain the outlet name")
print("\n".join(bad[:25])); sys.exit(1 if bad else 0)
