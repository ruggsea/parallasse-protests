# Task: were there YOUTH / STUDENT protests in {country}, 2026-09-25 to 2026-10-25?

Decide for ONE country: {country}. A yes needs protests in that window where young people, students or youth movements were the main actors
or a large visible part (school/university strikes, student marches, Gen-Z protests, youth climate marches, youth anti-government protests,
protests about education, jobs, prices, war/Gaza). Search with web_search, in English and the local language. Be quick: at most about 12 searches and fetches.

Rules
- Fetch pages ONLY with: `python3 ./scrapers/polite_fetch.py URL [--head N]` (robots-aware, logged, cached). Never curl/wget. GDELT is unreachable, do not try it. Wikipedia and news sites work.
- Never kill processes by name (no pkill/killall). Stay inside your working directory plus /tmp.
- Only report what you read in a fetched page. Never invent a URL, date or quote.
- Write the TSV to {OUT} (tab separated, header exactly):
  country	topic	start_date	scale	url1	date1	quote1	url2	date2	quote2
  ONE row, first field exactly `{country}`. topic = what the protests are about (one line). start_date = ISO date they began (may be earlier). scale = as stated in the sources. url1/url2 = two fetched articles on DIFFERENT hosts, each published 2026-09-25..2026-10-25 (date1/date2 = ISO date read from the page). quote1/quote2 = a sentence of at least 25 characters copied EXACTLY from that fetched page, showing the protest and young people. No tabs or newlines inside fields.
- If you probed at least 4 different sources and found no such protests, write one row: `NONE`, a topic naming the sources probed, empty other fields. (A NONE row is checked: the check probes some of the same sources.)
- Previous rejection (fix exactly this, empty on first attempt): {REJECTION}
