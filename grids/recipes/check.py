import json, re, sys, urllib.parse
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scrapers"))
from polite_fetch import fetch
part, start, cid = sys.argv[1:4]
try: rec = json.load(open(part))
except Exception as e: print(f"not valid JSON: {e}"); sys.exit(0)
for k in ("list_templates", "article_regex", "notes"):
    if k not in rec: print(f"missing key {k}"); sys.exit(0)
if not rec["list_templates"]: print("list_templates empty: only acceptable if notes say robots/blocked AND you tried the sitemap and archive pages; write that and re-submit is not possible, so try more first") if "robots" not in rec["notes"].lower() and "block" not in rec["notes"].lower() else None; sys.exit(0)
try: rx = re.compile(rec["article_regex"])
except re.error as e: print(f"article_regex invalid: {e}"); sys.exit(0)
bad, sample = [], []
for d in ("2026-09-30", "2026-10-10", "2026-10-20"):
    y, m, dd = d.split("-"); urls = set()
    for t in rec["list_templates"][:4]:
        u = t.replace("{YYYY}", y).replace("{MM}", m).replace("{DD}", dd)
        st, text, _ = fetch(u)
        if st != 200 or not text: bad.append(f"{d}: {u} gave status {st}"); continue
        blocks = re.findall(r"<url>(.*?)</url>", text, re.S)
        if blocks:
            for b in blocks:
                loc = re.search(r"<loc>\s*([^<\s]+)", b); lm = re.search(r"<lastmod>\s*(\d{4}-\d\d-\d\d)", b)
                if loc and rx.search(loc.group(1).replace("&amp;", "&")) and ("{DD}" in t or (lm and lm.group(1) == d)): urls.add(loc.group(1))
            continue
        for l in re.findall(r"""(?:href=["']|<loc>)\s*([^"'<>\s]+)""", text) + re.findall(r"https?://[^\s\"'<>]+", text):
            l = urllib.parse.urljoin(u, l.replace("&amp;", "&"))
            if rx.search(l): urls.add(l)
    if len(urls) < 15: bad.append(f"{d}: only {len(urls)} article URLs matched article_regex (need 15)")
    else: sample += sorted(urls)[:2]
if bad: print("\n".join(bad[:8])); sys.exit(0)
ok = 0
for u in sample[:4]:
    st, text, _ = fetch(u)
    t = re.sub(r"(?is)<(script|style)\b.*?</\1>|<[^>]+>", " ", text or "")
    if st == 200 and len(re.sub(r"\s+", " ", t)) >= 1500: ok += 1
if ok < 2: print(f"only {ok} of {len(sample[:4])} sample articles gave 1500+ characters of text (paywall or JS site?)")
