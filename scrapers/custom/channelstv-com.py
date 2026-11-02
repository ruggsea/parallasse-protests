#!/usr/bin/env python3
"""List channelstv.com article URLs published 2026-09-25..2026-10-25.

Route: Yoast sitemap index /sitemap.xml -> post-sitemapN.xml chunks (ascending N =
newest; verified chunk 188 = 2026-10-13..10-25, chunk 187 = 2026-09-16..10-13,
chunk 186 ends 2026-09-16). Date = the /YYYY/MM/DD/ permalink date in each URL
(site's own publication date), NOT <lastmod> (edit time).
Writes data/urls_custom/channelstv-com.tsv: URL<TAB>YYYY-MM-DD, unique, no header.
"""
import re
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(".")
sys.path.insert(0, str(ROOT / "scrapers"))
from polite_fetch import fetch  # noqa: E402

DOMAIN = "www.channelstv.com"
START = "2026-09-25"
END = "2026-10-25"
DATE_RE = re.compile(r"/(20\d{2})/(\d{2})/(\d{2})/")
OUT = ROOT / "data/urls_custom/channelstv-com.tsv"

def url_date(u):
    m = DATE_RE.search(u)
    if not m:
        return None
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"

def main():
    status, text, _ = fetch(f"https://{DOMAIN}/sitemap.xml")
    if status != 200:
        sys.exit(f"sitemap index: {status}")
    nums = [int(m) if m else 0 for m in
            re.findall(r"/post-sitemap(\d*)\.xml</loc>", text)]
    nums = sorted(set(nums), reverse=True)  # newest chunk first
    print(f"post-sitemap chunks available: {len(nums)}, newest {nums[0]}")
    chunks = nums

    urls = {}
    fails = 0
    for chunk in chunks:
        url = f"https://{DOMAIN}/post-sitemap{chunk}.xml"
        time.sleep(5)  # the site 404s bursts; a 188-request run was fully blocked for ~1 min
        status, text, _ = fetch(url)
        if status == 404:
            time.sleep(60)  # WAF cooldown observed to be ~60 s
            status, text, _ = fetch(url)
        if status != 200:
            print(f"WARN {chunk}: {status}, skipping")
            fails += 1
            if fails >= 3:
                sys.exit("3 consecutive non-200 chunks, aborting")
            continue
        fails = 0
        locs = re.findall(r"<loc>(https?://[^<]+)</loc>", text)
        pairs = [(u, url_date(u)) for u in locs if u.startswith(f"https://{DOMAIN}/20")]
        pairs = [(u, d) for u, d in pairs if d]
        dates = [d for _, d in pairs]
        if not dates:
            continue
        kept = [(u, d) for u, d in pairs if START <= d <= END]
        for u, d in kept:
            urls.setdefault(u, d)
        print(f"chunk {chunk}: {len(pairs)} urls, range {min(dates)}..{max(dates)}, kept {len(kept)}")
        # stop when this whole chunk is older than the window
        if max(dates) < START:
            print("oldest chunk fully before window, stopping")
            break

    OUT.parent.mkdir(parents=True, exist_ok=True)
    rows = sorted(urls.items(), key=lambda kv: (kv[1], kv[0]))
    with open(OUT, "w") as f:
        for u, d in rows:
            f.write(f"{u}\t{d}\n")
    per = Counter(d for _, d in rows)
    for d in sorted(per):
        print(f"{d}: {per[d]}")
    print(f"TOTAL {len(rows)} unique URLs -> {OUT}")
    if len(rows) < 15:
        sys.exit("too few URLs")

if __name__ == "__main__":
    main()
