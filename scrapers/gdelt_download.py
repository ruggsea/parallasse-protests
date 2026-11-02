#!/usr/bin/env python3
"""Download GDELT v2 15-minute GKG + export files for 2026-09-25..2026-10-25, keep protest rows only (discovery, not evidence).
Per slot writes data/gdelt/gkg/<ts>.tsv (rows whose V2Themes contain PROTEST: id date domain url themes locations tone), data/gdelt/gkg/<ts>.counts.json
(articles per domain, all rows = denominator) and data/gdelt/events/<ts>.tsv (export rows with EventRootCode 14). Idempotent: skips slots already done.
robots.txt of data.gdeltproject.org is empty (checked 2026-10-25) so proceed; 4 parallel downloads."""
import csv, io, json, sys, time, urllib.request, zipfile, datetime as dt
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
from pathlib import Path
R = Path(__file__).resolve().parent.parent
G, E = R/"data/gdelt/gkg", R/"data/gdelt/events"
UA = "ParallasseResearchBot/1.0 (+data-journalism study; contact rmlazza@gmail.com)"
csv.field_size_limit(10**8)
def get(url):
    for t in range(4):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60).read()
        except Exception as e:
            err = e; time.sleep(2 * (t + 1))
    raise err
def slot(ts):
    if (G/f"{ts}.counts.json").exists() and (E/f"{ts}.tsv").exists(): return "skip"
    base = f"https://data.gdeltproject.org/gdeltv2/{ts}"
    try:
        z = zipfile.ZipFile(io.BytesIO(get(base + ".gkg.csv.zip")))
        rows = csv.reader(io.TextIOWrapper(z.open(z.namelist()[0]), encoding="utf-8", errors="replace"), delimiter="\t", quoting=csv.QUOTE_NONE)
        cnt, out = Counter(), []
        for r in rows:
            if len(r) < 16: continue
            cnt[r[3]] += 1
            if "PROTEST" in r[8]: out.append([r[0], r[1], r[3], r[4], r[8], r[10], r[15].split(",")[0]])
        z = zipfile.ZipFile(io.BytesIO(get(base + ".export.CSV.zip")))
        ev = [l for l in io.TextIOWrapper(z.open(z.namelist()[0]), encoding="utf-8", errors="replace").read().split("\n") if len(l.split("\t")) > 28 and l.split("\t")[28] == "14"]
    except Exception as e:
        return f"FAIL {e}"
    (G/f"{ts}.tsv").write_text("\n".join("\t".join(x) for x in out))
    (E/f"{ts}.tsv").write_text("\n".join(ev))
    (G/f"{ts}.counts.json").write_text(json.dumps(cnt))
    return f"ok {len(out)} protest articles, {sum(cnt.values())} total, {len(ev)} events"
if __name__ == "__main__":
    t, end = dt.datetime(2026, 9, 25), dt.datetime(2026, 10, 25, 23, 45)
    slots = []
    while t <= end: slots.append(t.strftime("%Y%m%d%H%M%S")); t += dt.timedelta(minutes=15)
    slots = [s for s in slots if s <= dt.datetime.utcnow().strftime("%Y%m%d%H%M%S")]
    print(len(slots), "slots", flush=True)
    with ThreadPoolExecutor(4) as ex:
        for ts, res in zip(slots, ex.map(slot, slots)): print(ts, res, flush=True)
