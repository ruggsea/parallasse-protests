#!/usr/bin/env python3
"""Helper: parse a Domani (editorialedomani.it) listing page into (path, date) pairs.

Domani is a Next.js site; every listing page (section, tag, author, ?page=N) embeds its
GraphQL (urql) state as a nested JSON string in <script id="__NEXT_DATA__">.
Structure: props.urqlState[*].data -> JSON string -> page.slots[*].pagedTeasers.teasers[*]
           each teaser: {"date": ISO8601, "content": {"__typename": "Article"|..., "path": "/..."}}
"""
import json
import re


def _urql_payloads(html):
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.S)
    if not m:
        return []
    try:
        d = json.loads(m.group(1))
    except ValueError:
        return []
    out = []
    for _, v in (d.get("props", {}).get("urqlState") or {}).items():
        data = v.get("data") if isinstance(v, dict) else None
        if not isinstance(data, str):
            continue
        try:
            out.append(json.loads(data))
        except ValueError:
            continue
    return out


def _walk(o, key):
    """Yield every value stored under `key` anywhere in the tree."""
    stack = [o]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            for k, v in cur.items():
                if k == key:
                    yield v
                if isinstance(v, (dict, list)):
                    stack.append(v)
        elif isinstance(cur, list):
            stack.extend(cur)


def listing(html):
    """Return (total_hits, [(path, iso_date, typename, article_type, premium), ...])."""
    total = None
    rows = []
    for payload in _urql_payloads(html):
        for pt in _walk(payload, "pagedTeasers"):
            if not isinstance(pt, dict):
                continue
            if total is None and isinstance(pt.get("totalHits"), int):
                total = pt["totalHits"]
            for t in pt.get("teasers") or []:
                if not isinstance(t, dict):
                    continue
                c = t.get("content") or {}
                path = c.get("path")
                date = t.get("date")
                if not path or not date:
                    continue
                rows.append((path, date, c.get("__typename"), c.get("articleType"), bool(c.get("premium"))))
    return total, rows


if __name__ == "__main__":
    import sys
    sys.path.insert(0, "./scrapers")
    from polite_fetch import fetch
    url = sys.argv[1]
    s, t, p = fetch(url)
    print("status", s, "len", len(t or ""))
    total, rows = listing(t or "")
    print("totalHits", total, "rows", len(rows))
    for r in rows:
        print(r[1][:10], r[2], r[3], r[4], r[0][:90])
