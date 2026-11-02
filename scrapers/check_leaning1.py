#!/usr/bin/env python3
"""check_leaning1.py FILE -> prints problems, exit 1 if any. ONE-source leanings (second tier). Columns: outlet domain leaning url quote note.
url must be in the fetch cache (status 200); quote (>=15 chars) must occur in that page; leaning in LEAN (no unclassified here: omit the row instead)."""
import csv, json, re, sys, hashlib
from pathlib import Path
R = Path(__file__).resolve().parent.parent
LEAN = "far_left left centre_left centre centre_right right far_right".split()
norm = lambda t: re.sub(r"\W+", " ", t).lower().strip()
rows = list(csv.DictReader(open(sys.argv[1]), delimiter="\t")); bad = []
need = "outlet domain leaning url quote note".split()
if not rows or any(c not in rows[0] for c in need): print("header must be: " + " ".join(need)); sys.exit(1)
for r in rows:
    if r["leaning"] not in LEAN: bad.append(f"{r['outlet']}: leaning must be one of {LEAN}")
    f = R/"data/fetchcache"/(hashlib.sha256(r["url"].encode()).hexdigest()[:24]+".json")
    if not f.exists(): bad.append(f"{r['outlet']}: {r['url']} not fetched via polite_fetch"); continue
    j = json.load(open(f))
    if j["status"] != 200: bad.append(f"{r['outlet']}: {r['url']} status {j['status']}"); continue
    q = norm(r["quote"])
    if len(q) < 15 or q not in norm(j["text"] or ""): bad.append(f"{r['outlet']}: quote not found verbatim in {r['url']}")
print("\n".join(bad[:40])); sys.exit(1 if bad else 0)
