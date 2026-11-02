#!/usr/bin/env python3
"""Merge grids/countries2/out/*.tsv (accepted rows only) into data/countries.tsv: one row per candidate country with status YES or NONE_FOUND (NONE = our searches found nothing, not proof of nothing) or MISSING."""
import csv, glob
from pathlib import Path
R = Path(__file__).resolve().parent.parent
cells = list(csv.DictReader(open(R/"grids/countries2/cells.tsv"), delimiter="\t"))
WEAK = {"Bosnia and Herzegovina","Sweden","Thailand","North Macedonia","Sri Lanka","Vietnam","Tunisia","South Korea"}  # judged weak by reading rows 2026-10-25: local, small, or one source twice
cols = "country status confidence topic start_date scale url1 date1 quote1 url2 date2 quote2".split()
with open(R/"data/countries.tsv", "w", newline="") as o:
    w = csv.writer(o, delimiter="\t"); w.writerow(cols)
    for c in cells:
        f = R/f"grids/countries2/out/{c['id']}.tsv"
        if not f.exists(): w.writerow([c["country"], "MISSING", ""] + [""] * 9); continue
        r = list(csv.DictReader(open(f), delimiter="\t"))[0]
        if r["country"] == "NONE": w.writerow([c["country"], "NONE_FOUND", "", r["topic"]] + [""] * 8)
        else: w.writerow([c["country"], "YES", "weak" if c["country"] in WEAK else "ok"] + [r[k] for k in cols[3:]])
