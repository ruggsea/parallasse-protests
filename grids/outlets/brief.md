# Task: list the main news outlets of {country}, from one kind of source

Cell: country **{country}**, source **{source}**. Hint: {hint}
Goal: every news outlet of {country} that this source documents as a main outlet, in a broad sense: national dailies, TV news sites, wires, big online-only outlets, regional papers with national reach, news magazines/weeklies, public broadcaster, across the political spectrum (left, centre, right, tabloid and quality). Read the whole table/list (all pages), do not stop at the first few. Aim for 10-30 outlets from this source.

Rules
- Fetch pages ONLY with `python3 ./scrapers/polite_fetch.py URL [--head N]` (robots-aware, logged). Never curl/wget. Use web_search to find the right URL. Long pages: use --head 200000 and read in pieces.
- Never kill processes by name (no pkill/killall). Stay in your working directory plus /tmp. Never invent anything: every row needs a verbatim quote from the fetched page that contains the outlet name (a table row or sentence naming it, with its reach/rank/ownership if given).
- Write TSV to {OUT}, header exactly: outlet	domain	kind	url	quote
  domain = bare hostname of the outlet website (repubblica.it). kind one of: national_daily regional_daily tv wire online_only magazine public_broadcaster radio weekly. url = the fetched page. One row per outlet, no duplicate domains. No tabs/newlines in fields.
- Previous rejection (fix exactly this, empty on first attempt): {REJECTION}
