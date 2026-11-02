#!/usr/bin/env python3
"""List cartacapital.com.br articles published 2026-09-25..2026-10-25 -> data/urls_custom/cartacapital-com-br.tsv

Route: the WordPress REST API /wp-json/wp/v2/posts (allowed by robots.txt, which only blocks
/wp-admin, /wp-includes, /feed/rss2/, search). It returns each post's `date` field (publication
date in site-local time, America/Sao_Paulo) and canonical `link`. Yoast sitemaps (post-sitemap136..141)
carry lastmod (edit date) only, so they cannot be trusted for the publication date; the REST API is
the site's own dated listing. Paginate newest-first (per_page=100, date desc) until posts predate
the window, filter to the window locally, dedupe.
"""
import json
import sys
import time
from pathlib import Path
from urllib.parse import urlencode

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scrapers"))
from polite_fetch import fetch

ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "urls_custom" / "cartacapital-com-br.tsv"
BASE = "https://www.cartacapital.com.br/wp-json/wp/v2/posts"
WIN_START, WIN_END = "2026-09-25", "2026-10-25"


def main():
    q = {"per_page": 100,
         "after": "2026-09-24T23:59:59",
         "before": "2026-10-26T00:00:00",
         "orderby": "date",
         "order": "desc"}
    posts = {}
    page, stop = 1, False
    while not stop and page <= 80:
        url = f"{BASE}?{urlencode(q)}&page={page}"
        st, txt, _ = fetch(url)
        if st != 200:
            # slow down and retry this page a few times
            for _ in range(3):
                time.sleep(10)
                st, txt, _ = fetch(url)
                if st == 200:
                    break
            if st != 200:
                print(f"FAILED page {page}: HTTP {st}", file=sys.stderr)
                sys.exit(1)
        try:
            batch = json.loads(txt)
        except ValueError as e:
            print(f"BAD JSON page {page}: {e}", file=sys.stderr)
            sys.exit(1)
        if not isinstance(batch, list):
            print(f"UNEXPECTED response page {page}: {str(batch)[:200]}", file=sys.stderr)
            sys.exit(1)
        for p in batch:
            d = (p.get("date") or "")[:10]
            u = p.get("link") or ""
            if not u or not d:
                continue
            posts[u] = d  # newest-first: first sighting is the record
        # stop when the whole page predates the window (desc order)
        if len(batch) < 100 or (batch and (batch[-1].get("date") or "")[:10] < WIN_START):
            stop = True
        page += 1
        print(f"page {page - 1}: {len(batch)} posts (total {len(posts)})", file=sys.stderr)

    rows = [(u, d) for u, d in sorted(posts.items(), key=lambda r: (r[1], r[0])) if WIN_START <= d <= WIN_END]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w") as f:
        for u, d in rows:
            f.write(f"{u}\t{d}\n")
    per = {}
    for _, d in rows:
        per[d] = per.get(d, 0) + 1
    for d in sorted(per):
        print(f"{d}: {per[d]}")
    print(f"TOTAL: {len(rows)} URLs over {len(per)} days -> {OUT}")


if __name__ == "__main__":
    main()
