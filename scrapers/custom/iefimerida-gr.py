#!/usr/bin/env python3
"""List iefimerida.gr article URLs published 2026-09-25 .. 2026-10-25.

Route: robots.txt (permissive for article paths) names the only sitemap,
https://www.iefimerida.gr/sitemap.xml, a paginated index (sitemap.xml?page=N).
Each page is a flat <urlset> of ~10000 <url><loc>/<lastmod> pairs, ordered
ascending by lastmod. lastmod is +03:00 (Athens) and its date part matches the
page JSON-LD datePublished date on every sample checked (9/9 across
09-02..10-23). We walk pages backwards from the newest until a whole page is
older than the window start, so the script stays correct if the sitemap grows.
"""
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scrapers"))
from polite_fetch import fetch  # noqa: E402

BASE = "https://www.iefimerida.gr"
START, END = "2026-09-25", "2026-10-25"
OUT = Path("data/urls_custom/iefimerida-gr.tsv")


def main():
    status, text, _ = fetch(BASE + "/sitemap.xml")
    if status != 200 or not text:
        raise SystemExit(f"sitemap index failed: {status}")
    pages = re.findall(r"<loc>(https://www\.iefimerida\.gr/sitemap\.xml\?page=\d+)</loc>", text)
    if not pages:
        raise SystemExit("no ?page= entries in sitemap index")
    # pages are ascending by lastmod; walk backwards from the newest
    order = sorted(set(pages), key=lambda u: int(u.rsplit("=", 1)[1]))
    urls = {}
    for page_url in reversed(order):
        status, text, _ = fetch(page_url)
        if status != 200 or not text:
            print(f"WARNING: {page_url} -> {status}, skipping", file=sys.stderr)
            continue
        locs = re.findall(r"<loc>(.*?)</loc>", text)
        mods = re.findall(r"<lastmod>(.*?)</lastmod>", text)
        in_window = 0
        newest = ""
        for u, m in zip(locs, mods):
            d = m[:10]
            newest = max(newest, d)
            if START <= d <= END:
                in_window += 1
                urls.setdefault(u, d)
        print(f"{page_url}: {len(locs)} urls, newest {newest or 'n/a'}, in-window {in_window}")
        if newest and newest < START:  # whole page predates the window
            break
    OUT.parent.mkdir(parents=True, exist_ok=True)
    rows = sorted(urls.items(), key=lambda kv: (kv[1], kv[0]))
    with OUT.open("w", encoding="utf-8") as f:
        for u, d in rows:
            f.write(f"{u}\t{d}\n")
    cnt = Counter(d for _, d in rows)
    print(f"wrote {len(rows)} unique urls to {OUT}")
    for d in sorted(cnt):
        print(f"  {d}: {cnt[d]}")


if __name__ == "__main__":
    main()
