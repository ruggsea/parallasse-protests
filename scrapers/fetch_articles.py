#!/usr/bin/env python3
"""fetch_articles.py ID [--workers N] : fetch every URL in data/urls/<ID>.tsv through polite_fetch (robots, rate limit, logged; raw html not cached)
and extract title/date/text with trafilatura into data/articles/<ID>.jsonl (one json per url: url, listed_date, status, title, date, text).
Resumable: urls already in the jsonl are skipped. Transient failures (status 0, 5xx, 429) are retried on the next run, max 3 tries, tracked in the row ('tries')."""
import json, sys, threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from polite_fetch import fetch
import trafilatura
R = Path(__file__).resolve().parent.parent
cid = sys.argv[1]; workers = int(sys.argv[sys.argv.index("--workers") + 1]) if "--workers" in sys.argv else 4
src = R/f"data/urls/{cid}.tsv"; dst = R/f"data/articles/{cid}.jsonl"; dst.parent.mkdir(parents=True, exist_ok=True)
done = {}
if dst.exists():
    for l in open(dst):
        r = json.loads(l); done[r["url"]] = r
todo = [l.rstrip("\n").split("\t")[:2] for l in open(src) if l.startswith("http")]
todo = [(u, d) for u, d in todo if u not in done or (done[u]["status"] in (0, 429, 500, 502, 503, 504) and done[u].get("tries", 1) < 3)]
lock = threading.Lock(); out = open(dst, "a"); n = [0]
def work(ud):
    u, d = ud
    st, html, _ = fetch(u, cache=False)
    row = {"url": u, "listed_date": d, "status": st, "tries": done.get(u, {}).get("tries", 0) + 1}
    if st == 200 and html:
        meta = trafilatura.extract(html, output_format="json", with_metadata=True, favor_precision=True)
        if meta:
            m = json.loads(meta); row.update(title=m.get("title"), date=m.get("date"), text=m.get("text"))
    with lock:
        out.write(json.dumps(row, ensure_ascii=False) + "\n"); out.flush(); n[0] += 1
        if n[0] % 200 == 0: print(cid, n[0], "of", len(todo), flush=True)
with ThreadPoolExecutor(workers) as ex: list(ex.map(work, todo))
print(cid, "finished", n[0], flush=True)
