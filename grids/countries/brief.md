# Task: find countries with YOUTH / STUDENT / YOUNG-PEOPLE protests, 2026-09-25 to 2026-10-25

Cell: region **{region}**, source kind **{kind}**. Your goal: list every country in that region that had protests in this window where
young people, students or youth movements were the main actors or a large visible part (school/university strikes, student marches,
Gen-Z protests, youth climate marches, youth anti-government protests, protests about education, jobs, cost of living, war/Gaza, etc.).
Be complete for your region: search many sources of your kind, then other angles. Do not stop at the first country.

Rules
- Fetch pages ONLY with: `python3 ./scrapers/polite_fetch.py URL [--head N]` (robots-aware, logged, cached). Never curl/wget. Use web_search to find URLs, then fetch them with the tool above.
- Never kill processes by name (no pkill/killall). Stay inside your working directory plus /tmp.
- Only report what you read in a fetched page. Never invent a URL, date or quote. If you find nothing, say so with a row `NONE` (see below).
- Source kind hints: wire = Reuters/AP/AFP/EFE/ANSA/Anadolu pages; wikipedia = Wikipedia "Portal:Current events/2026 <Month> <day>" pages and "List of protests in 2026"; gdelt = GDELT DOC API (https://api.gdeltproject.org/api/v2/doc/doc?query=...&mode=artlist&format=json&timespan=1month) ; acled = ACLED public pages/dashboards if open; local = national news sites and search in local languages; ngo = student unions, Amnesty/HRW/Crisis Group pages.
- Write the TSV to {OUT} (tab separated, header exactly):
  country	topic	start_date	scale	url1	date1	quote1	url2	date2	quote2
  one row per country. topic = what the protests are about (one line). start_date = ISO date the protests began (may be before 2026-09-25 if so). scale = e.g. "tens of thousands, 12 cities" as stated in the sources. url1/url2 = two fetched articles on DIFFERENT hosts, each published in 2026-09-25..2026-10-25 (date1/date2 = ISO publication date, read from the page). quote1/quote2 = a sentence of at least 25 characters copied EXACTLY from that fetched page, showing the protest and young people. No tabs or newlines inside fields.
- If after probing at least 4 sources you find no such country in your region, write one row: NONE, a topic naming the sources probed, then empty other fields.
- Previous rejection (fix exactly this, empty on first attempt): {REJECTION}
