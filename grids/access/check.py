import json, os, sys, datetime
part, start, cid = sys.argv[1:4]
root = "."
WIN_START = datetime.date(2026, 9, 25); WIN_END = datetime.date(2026, 10, 25)
out = os.path.join(root, "data", "articles", cid + ".jsonl")
if not os.path.exists(out):
    print("no output file data/articles/%s.jsonl" % cid); sys.exit(0)
rows = []; bad = 0
for line in open(out):
    line = line.strip()
    if not line: continue
    try: rows.append(json.loads(line))
    except Exception: bad += 1
if bad: print("%d unparseable JSON lines" % bad); sys.exit(0)
if not rows: print("output file is empty"); sys.exit(0)
seen = set(); inwin = 0; dated = 0; withtext = 0
for r in rows:
    u = r.get("url")
    if not u: continue
    if u in seen: print("duplicate url: %s" % u); sys.exit(0)
    seen.add(u)
    d = r.get("date") or r.get("listed_date")
    if d:
        try:
            dd = datetime.date.fromisoformat(str(d)[:10])
            if WIN_START <= dd <= WIN_END: inwin += 1
            dated += 1
        except Exception: pass
    t = r.get("text") or ""
    if len(t) >= 200: withtext += 1
if inwin < 20: print("only %d articles dated inside 2026-09-25..2026-10-25 (need 20); rows=%d dated=%d" % (inwin, len(rows), dated)); sys.exit(0)
if withtext < 20: print("only %d rows carry 200+ chars of text (need 20); rows=%d" % (withtext, len(rows))); sys.exit(0)
print("OK %s: rows=%d in_window=%d with_text=%d dated=%d" % (cid, len(rows), inwin, withtext, dated))
sys.exit(1)
