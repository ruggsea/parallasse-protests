#!/usr/bin/env python3
"""List article URLs published by The Financial Express (Bangladesh),
thefinancialexpress.com.bd, from 2026-09-25 to 2026-10-25 (both inclusive).

Route: the site's own pages (Next.js) call a JSON posts API on a separate
host, https://api.thefinancialexpress.com.bd/api/en/posts?limit=1000, which
returns {"items":[{id,title,slug,datetime,category,...}], "nextPageUrl",
"hasPages"}. The api host's robots.txt (User-agent: * / Disallow: <empty>)
allows everything; the main host's robots.txt disallows only /api/ on the
main host, not on the api subdomain. Each item's "datetime" is the site's
own publication timestamp (the article pages repeat it verbatim as
datePublished), and "slug" is the article's full path on the main host.

We walk the cursor-paginated stream from newest backwards until we reach
posts older than the window. The server drops the limit param in its
nextPageUrl, so we re-append limit=1000 to every follow-up page.

Output: data/urls_custom/thefinancialexpress-com-bd.tsv  (URL<TAB>YYYY-MM-DD)
"""
import json
import sys
import time
from collections import Counter

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scrapers"))
from polite_fetch import fetch  # noqa: E402

API = "https://api.thefinancialexpress.com.bd/api/en/posts"
LIMIT = "limit=1000"
BASE = "https://thefinancialexpress.com.bd"
START = "2026-09-25"
END = "2026-10-25"
OUT = "data/urls_custom/thefinancialexpress-com-bd.tsv"
MAX_PAGES = 400


def get_page(url, tries=3):
    for attempt in range(tries):
        status, text, _ = fetch(url)
        if status == 200 and text:
            return json.loads(text)
        print(f"  page fetch HTTP {status}, retry {attempt + 1} in 20s", flush=True)
        time.sleep(20)
    raise SystemExit(f"aborted: API kept failing (HTTP {status}) on {url}")


def with_limit(url):
    sep = "&" if "?" in url else "?"
    if "limit=" in url:
        return url
    return f"{url}{sep}{LIMIT}"


def main():
    urls = {}          # article url -> date (first/newest wins)
    per_day = Counter()
    url = f"{API}?{LIMIT}"
    pages = 0
    stop_reason = None
    while url and pages < MAX_PAGES and not stop_reason:
        data = get_page(url)
        pages += 1
        items = data.get("items") or []
        for it in items:
            dt = it.get("datetime") or ""
            date = dt[:10]
            if len(date) < 10:
                continue
            if date < START:
                stop_reason = "reached posts older than window start"
                continue
            if date > END:
                continue
            slug = (it.get("slug") or "").strip()
            if not slug.startswith("/"):
                continue
            aurl = BASE + slug
            if aurl in urls:
                continue
            urls[aurl] = date
            per_day[date] += 1
        if not items:
            oldest = min((i.get("datetime", "")[:10] for i in items), default="?")
            print(f"  page {pages}: {len(urls)} urls so far, oldest item {oldest}", flush=True)
        if not (data.get("hasPages") and data.get("nextPageUrl")):
            stop_reason = stop_reason or "API reports no further pages"
            break
        url = with_limit(data["nextPageUrl"])

    with open(OUT, "w") as f:
        for aurl in sorted(urls, key=lambda u: (urls[u], u)):
            f.write(f"{aurl}\t{urls[aurl]}\n")

    print(f"pages fetched: {pages} (stop: {stop_reason})")
    print(f"wrote {len(urls)} unique URLs to {OUT}")
    print("per-day counts:")
    for day in sorted(per_day):
        print(f"  {day}\t{per_day[day]}")
    missing = [d for d in (START, "2026-09-30", "2026-10-10", "2026-10-20", END)
               if per_day.get(d, 0) == 0]
    if missing:
        print(f"WARNING: zero URLs for: {missing}", file=sys.stderr)


if __name__ == "__main__":
    main()
