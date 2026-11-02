#!/usr/bin/env python3
"""List Vizion Plus (vizionplus.tv) article URLs published 2026-09-25 .. 2026-10-25.

Route: the site runs WordPress and its REST API is open to us:
    /wp-json/wp/v2/posts?per_page=100&page=N&after=...&before=...&orderby=date&order=asc
It returns, per post, `link` (canonical article URL) and `date` (the publication date the
site itself states, site-local time). One request per 100 posts; 25 requests cover the window.

Why the extra content filter: a large share of this outlet's items are stubs (a headline and
two or three sentences). The study needs articles with body text, so a post is kept only if
its own body (content.rendered, tags stripped) is at least MIN_BODY_CHARS characters. Measured
on this window: a kept post yields at least body length + ~60 chars of extracted page text, so
MIN_BODY_CHARS=1600 keeps the extracted article text safely above 1500 chars.

Output: data/urls_custom/vizionplus-tv.tsv, lines "URL<TAB>YYYY-MM-DD", no header, unique URLs.
"""
import sys
import os
import re
import json
import html
import time
from collections import defaultdict
from datetime import datetime, timedelta

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scrapers"))
from polite_fetch import fetch  # noqa: E402

BASE = "https://www.vizionplus.tv/wp-json/wp/v2/posts"
START = "2026-09-25"
END = "2026-10-25"
PER_PAGE = 100
MIN_BODY_CHARS = 1600
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(os.path.join(HERE, "..", "..", "data", "urls_custom", "vizionplus-tv.tsv"))


def body_chars(rendered_html):
    """Plain-text length of the post body as the site stores it."""
    t = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", rendered_html or "", flags=re.S)
    t = re.sub(r"<[^>]+>", " ", t)
    t = html.unescape(t)
    return len(re.sub(r"\s+", " ", t).strip())


def get_json(url, tries=3):
    for i in range(tries):
        status, text, _ = fetch(url)
        if status == 200:
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass
        elif status == 400:
            # WP answers 400 "rest_post_invalid_page_number" past the last page.
            return None
        elif status in (429, 403, 503, 0):
            time.sleep(5 * (i + 1))
            continue
        else:
            return None
        time.sleep(3 * (i + 1))
    return None


def main():
    after = f"{START}T00:00:00"
    before = f"{(datetime.fromisoformat(END) + timedelta(days=1)).date()}T00:00:00"
    seen = {}
    dates = {}
    page = 1
    while page <= 200:
        url = (f"{BASE}?per_page={PER_PAGE}&page={page}"
               f"&after={after}&before={before}&orderby=date&order=asc"
               "&_fields=id,date,link,content")
        data = get_json(url)
        if not data:
            if page == 1:
                print("REST API returned nothing on page 1: cannot build the list", file=sys.stderr)
                return 1
            break
        if not isinstance(data, list) or not data:
            break
        for item in data:
            link = (item.get("link") or "").strip()
            date = (item.get("date") or "")[:10]
            if not link or not re.fullmatch(r"\d{4}-\d\d-\d\d", date):
                continue
            if not (START <= date <= END):
                continue
            n = body_chars((item.get("content") or {}).get("rendered", ""))
            prev = seen.get(link)
            if prev is not None and prev >= MIN_BODY_CHARS:
                continue
            seen[link] = n
            dates[link] = date
        page += 1

    kept = {u: d for u, d in dates.items() if seen[u] >= MIN_BODY_CHARS}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    per_day = defaultdict(int)
    with open(OUT, "w", encoding="utf-8") as f:
        for u in sorted(kept):
            f.write(f"{u}\t{kept[u]}\n")
            per_day[kept[u]] += 1

    print(f"posts seen in window: {len(dates)}; kept with body >= {MIN_BODY_CHARS} chars: {len(kept)}")
    print(f"wrote {OUT}")
    for day in sorted(per_day):
        print(f"{day}\t{per_day[day]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
