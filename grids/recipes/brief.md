# Task: find how to list ALL articles of {outlet} ({domain}, {country}) published on a given day, from its own site

Goal: a recipe that, for any date between 2026-09-25 and 2026-10-25, gives the URLs of that day's articles. Not RSS (RSS only shows the latest items, our window is already over). Look for: date-based archive pages (e.g. https://www.example.it/archivio/2026/10/10/), daily or monthly XML sitemaps (read https://{domain}/robots.txt via the fetcher for `Sitemap:` lines; also /sitemap.xml, /sitemap_index.xml, /news-sitemap.xml, /sitemaps/...), section archive pages with date paging. Try `www.{domain}` and `{domain}`.

Rules
- Fetch pages ONLY with `python3 ./scrapers/polite_fetch.py URL --raw --head 300000` (robots-aware, logged, gunzips .gz sitemaps; --raw keeps the XML/HTML so you can read links). Never curl/wget. Never kill processes by name. Stay in your working directory plus /tmp. Do not invent URLs: test each template yourself for at least two dates.
- If the robots.txt disallows the archive or the site blocks us, say so in `notes` and write an empty list_templates.
- Write JSON to {OUT}:
  {"list_templates": ["https://www.{domain}/archivio/{YYYY}/{MM}/{DD}/", ...], "article_regex": "<python regex matching an article URL (absolute) inside those pages>", "notes": "one line"}
  Placeholders {YYYY} {MM} {DD} only. A list_template may be a daily archive page, a daily sitemap, or a monthly sitemap (then {DD} is absent; the checker takes all article URLs it finds and keeps those whose URL or lastmod shows the date, so prefer templates that are per day). Up to 4 templates (pages are unioned, e.g. one per section). article_regex must match absolute article URLs on {domain} (use full URLs from the page, or write the regex for the path and the checker will urljoin relative links).
- The check expands the templates for 2026-09-30, 2026-10-10 and 2026-10-20, fetches them, and needs at least 15 distinct article URLs for each date, then fetches 2 articles and needs readable text of at least 1500 characters. Test the same way before you finish.
- Previous rejection (fix exactly this, empty on first attempt): {REJECTION}
