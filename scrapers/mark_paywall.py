"""Per outlet: count articles with full text vs paywall_truncated (stored text < 1500 chars, or Domani premium URL).
Writes data/paywall_counts.tsv. The flag itself is recomputed from the jsonl by analysis code with the same rule (see is_truncated)."""
import json
from pathlib import Path
R = Path(__file__).resolve().parent.parent
premium = set(open(R/"data/urls_custom/editorialedomani-it.premium.txt").read().split()) if (R/"data/urls_custom/editorialedomani-it.premium.txt").exists() else set()
def is_truncated(row):
    return row["url"] in premium or len((row.get("text") or "")) < 1500
if __name__ == "__main__":
    rows = []
    for f in sorted((R/"data/articles").glob("*.jsonl")):
        n = full = no_text = 0
        for l in open(f):
            r = json.loads(l)
            if r["status"] != 200: continue
            n += 1; no_text += not r.get("text"); full += not is_truncated(r)
        rows.append((f.stem, n, full, n - full, no_text))
    with open(R/"data/paywall_counts.tsv", "w") as o:
        o.write("outlet\tfetched_200\tfull\tpaywall_truncated\tno_text\n")
        for r in rows: o.write("\t".join(map(str, r)) + "\n")
    print(len(rows), "outlets;", sum(r[1] for r in rows), "articles,", sum(r[2] for r in rows), "full")
