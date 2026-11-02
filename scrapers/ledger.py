#!/usr/bin/env python3
"""Funnel ledger: one row per outlet in data/outlets/*.tsv -> data/ledger.tsv (state + reason code), and per-country coverage.
Reason codes come from the recipe notes: robots (disallowed by robots.txt), waf (403/429/WAF), no_archive (site answers, no way to list days), thin (<15/day), pending."""
import csv, json, re
from pathlib import Path
from collections import defaultdict
R = Path(__file__).resolve().parent.parent
cells = list(csv.DictReader(open(R/"grids/recipes/cells.tsv"), delimiter="\t"))
def lines(p): return sum(1 for _ in open(p, errors="replace")) if p.exists() else 0
def code(notes):
    n = notes.lower()
    if "did not write" in n: return "worker_no_output"
    if re.search(r"403|429|waf|cloudflare|captcha|access denied", n): return "waf_403_429"
    if re.search(r"robots", n) and re.search(r"disallow|blocks? (us|all|our)|forbid", n): return "robots_disallow"
    if re.search(r"\bjs\b|javascript|\bspa\b|client-side|no news text", n): return "js_site"
    if re.search(r"2 days|last \d+|only .*newest|no sitemap|archive", n): return "no_archive"
    return "other"
failed = set(json.load(open(R/"grids/recipes/status.json"))["failed_ids"]); lastwhy = {}
for l in open(R/"grids/recipes/ledger.jsonl"):
    j = json.loads(l); lastwhy[j["id"]] = j.get("reasons", "")
rows = []
for c in cells:
    i = c["id"]; rf = R/"grids/recipes"/"out"/f"{i}.json"; fb = R/"grids/italy_fallback"/"out"/f"{i}.json"
    cu = R/"grids/custom"/"out"/f"{i}.json"
    rec = json.load(open(fb if fb.exists() else rf)) if (fb.exists() or rf.exists()) else None
    crec = json.load(open(cu)) if cu.exists() else None
    art = lines(R/"data/articles"/f"{i}.jsonl")
    # a custom scraper writes its URL list to data/urls_custom/ and a copy is placed in data/urls/;
    # take whichever exists (la-repubblica-it had 4408 in urls_custom and 0 in urls, reported as 0).
    urls = lines(R/"data/urls"/f"{i}.tsv") or lines(R/"data/urls_custom"/f"{i}.tsv")
    if art and (R/"data/articles"/f"{i}.done").exists(): st, why = "articles", ""
    elif art: st, why = "fetching", ""
    # The custom grid is consulted BEFORE the recipes verdict: many outlets were later
    # collected by a custom scraper (grids/custom/out/<id>.json) after the recipes grid
    # failed them, and the recipes status.json/ledger.jsonl were never updated. Reading
    # only the recipes files reported those as recipe_failed/worker_no_output with articles
    # already on disk (180 outlets, found 2026-10-29).
    elif crec is not None: st, why = "custom_ok", ""
    elif rec and rec.get("list_templates"): st, why = "recipe_ok_no_articles_yet", ""
    elif rec: st, why = "rejected", code(str(rec.get("notes")))
    elif i in failed: st, why = "recipe_failed", code(lastwhy.get(i, ""))
    else: st, why = "pending", ""
    rows.append(dict(id=i, country=c["country"], outlet=c["outlet"], domain=c["domain"], state=st, reason=why, urls=max(urls-1, 0), articles=art, fallback=int(fb.exists())))
with open(R/"data/ledger.tsv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]), delimiter="\t"); w.writeheader(); w.writerows(rows)
per = defaultdict(lambda: [0, 0])
for r in rows: per[r["country"]][0] += 1; per[r["country"]][1] += r["state"] == "articles"
print("states:", {s: sum(r["state"] == s for r in rows) for s in sorted({r["state"] for r in rows})})
print("reasons:", {s: sum(r["reason"] == s for r in rows) for s in sorted({r["reason"] for r in rows}) if s})
it = [r for r in rows if r["country"] == "Italy"]; print("Italy outlets with articles:", sum(r["state"] == "articles" for r in it), "of", len(it))
