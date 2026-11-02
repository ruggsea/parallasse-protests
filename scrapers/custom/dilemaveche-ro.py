#!/usr/bin/env python3
"""dilemaveche.ro (Dilema Veche, RO) -> data/urls_custom/dilemaveche-ro.tsv

Route: robots.txt is permissive and advertises /sitemap/index, but every sitemap in
that index is stale (category sitemaps stop at 2024-02-28), so the sitemap route is
useless for 2026.  The site is a SvelteKit front-end over the "reperio" CMS: each
section page embeds `var reperioContext = {...}` whose category.content.items[] carry
`url`, `created_at` (publish time, UTC) and `published_at`.  We collect the section
list from the site's own top menu (reperioContext.global_blocks.TopMenu_main_menu),
plus the top-level section slugs still listed in the (stale) sitemap index, and read
50 recent items per section.  Listed date = date part of the item's created_at (UTC).
"""
import sys, os, re, json, datetime

sys.path.insert(0, "scrapers")
from polite_fetch import fetch

ROOT = "."
OUT = os.path.join(ROOT, "data/urls_custom/dilemaveche-ro.tsv")
HOST = "https://dilemaveche.ro"
START = datetime.date(2026, 9, 25)
END = datetime.date(2026, 10, 25)


def get(url):
    try:
        status, text, _ = fetch(url)
    except Exception as e:
        print("ERR", url, e, file=sys.stderr)
        return None
    if status != 200 or not text:
        print("FAIL", status, url, file=sys.stderr)
        return None
    return text


CTX = re.compile(r"reperioContext\s*=\s*")


def parse_context(html):
    """Return the reperioContext dict embedded in a page, or None."""
    m = CTX.search(html)
    if not m:
        return None
    i = m.end()
    j = html.find("</script>", i)
    if j < 0:
        return None
    blob = html[i:j].strip().rstrip(";").strip()
    try:
        return json.loads(blob)
    except ValueError:
        return None


def walk_items(obj, out):
    """Collect every dict that looks like a content item."""
    if isinstance(obj, dict):
        if "url" in obj and ("created_at" in obj or "published_at" in obj) and "slug" in obj:
            out.append(obj)
        for v in obj.values():
            walk_items(v, out)
    elif isinstance(obj, list):
        for v in obj:
            walk_items(v, out)


def sections():
    urls = []
    html = get(HOST + "/")
    if html:
        ctx = parse_context(html)
        if ctx:
            items = (ctx.get("global_blocks", {}).get("TopMenu_main_menu", {})
                     .get("data", {}).get("items") or [])
            for m in items:
                u = m.get("url") or ""
                if u.startswith("/sectiune/"):
                    urls.append(u)
                for c in (m.get("childs") or []):
                    cu = c.get("url") or ""
                    if cu.startswith("/sectiune/"):
                        urls.append(cu)
    # top-level section slugs still named by the (stale) sitemap index
    idx = get(HOST + "/sitemap/index")
    if idx:
        for loc in re.findall(r"<loc>(.*?)</loc>", idx):
            m = re.search(r"/sitemap/category/sectiune/([a-z0-9-]+)$", loc)
            if m:
                urls.append("/sectiune/" + m.group(1))
    seen, res = set(), []
    for u in urls:
        if u not in seen:
            seen.add(u)
            res.append(u)
    return res


def main():
    rows = {}
    secs = sections()
    print("sections:", len(secs), file=sys.stderr)
    for s in secs:
        html = get(HOST + s)
        if not html:
            continue
        ctx = parse_context(html)
        if not ctx:
            print("no ctx", s, file=sys.stderr)
            continue
        items = []
        walk_items(ctx, items)
        for it in items:
            u = it.get("url")
            if not isinstance(u, str) or not u.startswith("http"):
                continue
            stamp = it.get("created_at") or it.get("published_at") or ""
            m = re.match(r"(\d{4}-\d{2}-\d{2})", stamp)
            if not m:
                continue
            d = datetime.date.fromisoformat(m.group(1))
            if START <= d <= END:
                rows[u] = m.group(1)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    per_day = {}
    with open(OUT, "w") as f:
        for u in sorted(rows):
            f.write("%s\t%s\n" % (u, rows[u]))
            per_day[rows[u]] = per_day.get(rows[u], 0) + 1
    print("total", len(rows))
    d = START
    while d <= END:
        k = d.isoformat()
        print(k, per_day.get(k, 0))
        d += datetime.timedelta(days=1)


if __name__ == "__main__":
    main()
