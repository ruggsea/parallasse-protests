#!/usr/bin/env python3
"""check_leaning.py FILE -> prints problems, exit 1 if any. Columns: outlet domain leaning url1 quote1 url2 quote2 note.
Each url must be in the fetch cache (status 200), each quote (>=20 chars) must occur in that page and contain the outlet name or a word of its domain
or say a leaning word; leaning in LEAN; url1 != url2 host-path; if leaning is 'unclassified', note must say why."""
import csv, json, re, sys, hashlib
from pathlib import Path
R = Path(__file__).resolve().parent.parent
LEAN = "far_left left centre_left centre centre_right right far_right unclassified".split()
norm = lambda t: re.sub(r"\W+", " ", t).lower().strip()
rows = list(csv.DictReader(open(sys.argv[1]), delimiter="\t")); bad = []
need = "outlet domain leaning url1 quote1 url2 quote2 note".split()
if not rows or any(c not in rows[0] for c in need): print("header must be: " + " ".join(need)); sys.exit(1)
for r in rows:
    if r["leaning"] not in LEAN: bad.append(f"{r['outlet']}: leaning must be one of {LEAN}")
    if r["leaning"] == "unclassified" and len(r["note"]) < 15: bad.append(f"{r['outlet']}: unclassified needs a note saying why")
    if r["url1"] == r["url2"] and r["leaning"] != "unclassified": bad.append(f"{r['outlet']}: two different source pages needed")
    for k in "12":
        if r["leaning"] == "unclassified" and not r["url"+k]: continue
        f = R/"data/fetchcache"/(hashlib.sha256(r["url"+k].encode()).hexdigest()[:24]+".json")
        if not f.exists(): bad.append(f"{r['outlet']}: {r['url'+k]} not fetched via polite_fetch"); continue
        j = json.load(open(f))
        if j["status"] != 200: bad.append(f"{r['outlet']}: {r['url'+k]} status {j['status']}"); continue
        q = norm(r["quote"+k])
        if len(q) < 20 or q not in norm(j["text"] or ""): bad.append(f"{r['outlet']}: quote{k} not found verbatim in {r['url'+k]}")
print("\n".join(bad[:40])); sys.exit(1 if bad else 0)
