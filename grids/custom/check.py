import json, re, subprocess, sys, shutil
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scrapers"))
from polite_fetch import fetch
import trafilatura
from datetime import date
part, start, cid = sys.argv[1:4]
R = __import__("pathlib").Path(__file__).resolve().parents[2]
try: rec = json.load(open(part))
except Exception as e: print(f"not valid JSON: {e}"); sys.exit(0)
sp = R/f"scrapers/custom/{cid}.py"
if rec.get("script") != f"scrapers/custom/{cid}.py" or not sp.exists(): print(f"script missing: expected scrapers/custom/{cid}.py"); sys.exit(0)
out = R/f"data/urls_custom/{cid}.tsv"
if not out.exists(): print("data/urls_custom/%s.tsv missing: run your script yourself to the end and leave its output there" % cid); sys.exit(0)
if out.stat().st_mtime < sp.stat().st_mtime:
    try: p = subprocess.run([sys.executable, str(sp)], cwd=R, timeout=200, capture_output=True, text=True)
    except subprocess.TimeoutExpired: print("the tsv was older than the script and the script did not finish in 200 s when rerun by the check; make it faster"); sys.exit(0)
    if p.returncode: print("rerunning the script (tsv was older) failed: " + p.stderr[-300:]); sys.exit(0)
    if out.stat().st_mtime < sp.stat().st_mtime: print("the script did not write its tsv when rerun"); sys.exit(0)
rows = [l.rstrip("\n").split("\t") for l in open(out) if l.strip()]
if any(len(r) != 2 or not re.fullmatch(r"\d{4}-\d\d-\d\d", r[1]) for r in rows): print("every line must be URL<TAB>YYYY-MM-DD"); sys.exit(0)
urls = [r[0] for r in rows]
if len(set(urls)) != len(urls): print(f"{len(urls) - len(set(urls))} duplicate URLs"); sys.exit(0)
if any(not ("2026-09-25" <= r[1] <= "2026-10-25") for r in rows): print("dates outside the window: " + str([r for r in rows if not ("2026-09-25" <= r[1] <= "2026-10-25")][:3])); sys.exit(0)
per = defaultdict(list)
for u, d in rows: per[d].append(u)
bad = [f"{d}: {len(per[d])} URLs (need 15)" for d in ("2026-09-30", "2026-10-10", "2026-10-20") if len(per[d]) < 15]
thin = len(per) >= 25 and len(rows) >= 100 and all(len(per[d]) >= 5 for d in ("2026-09-30", "2026-10-10", "2026-10-20"))
if bad and thin: rec["low_volume"] = True   # manager rule 2026-10-26: thin but continuous = low_volume
low_volume = bool(bad)
if low_volume and (not rec.get("low_volume") or len(rows) < 10):
    print("\n".join(bad) + f"; total {len(rows)} URLs over {len(per)} days. If the outlet really publishes fewer, set \"low_volume\": true in the JSON, with the three day counts in notes, and keep at least 10 URLs"); sys.exit(0)
ok, msgs = 0, []
for d in ("2026-09-30", "2026-10-10", "2026-10-20"):
    for u in (sorted(per[d])[1::7] or sorted(per[d]))[:2]:
        st, html, _ = fetch(u)
        txt = trafilatura.extract(html or "", with_metadata=True, output_format="json")
        j = json.loads(txt) if txt else {}
        t = j.get("text", ""); pd = (j.get("date") or "")[:10]
        try: near = abs((date.fromisoformat(pd) - date.fromisoformat(d)).days) <= 1
        except ValueError: near = False
        cjk = sum(1 for ch in t if '\u3040' <= ch <= '\u9fff' or '\uac00' <= ch <= '\ud7af') > len(t) * 0.3
        if st == 200 and len(t) >= (500 if cjk else 1500) and near: ok += 1
        else: msgs.append(f"{u}: status {st}, {len(t)} chars, page date '{pd}' vs listed {d}")
if ok < 4: print(f"only {ok} of 6 samples good (need 4): " + "; ".join(msgs[:3])); sys.exit(0)
shutil.copy(out, R/f"data/urls/{cid}.tsv")
if low_volume:
    with open(R/"data/low_volume.tsv", "a") as f: f.write(f"{cid}\t{len(rows)}\t" + "\t".join(str(len(per[d])) for d in ("2026-09-30", "2026-10-10", "2026-10-20")) + "\n")
