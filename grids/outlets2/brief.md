# Task: list main news outlets of {country}: {focus}

Find the outlets of this kind that are main ones in {country}, across the political spectrum. Be quick: one or two good pages (the hint names them), at most about 10 fetches. Aim for 8-20 outlets.

Rules
- Fetch pages ONLY with `python3 ./scrapers/polite_fetch.py URL [--head N]` (robots-aware, logged). Never curl/wget. Wikipedia works and is the recommended start; use web_search only if a page is missing.
- Never kill processes by name (no pkill/killall). Stay in your working directory plus /tmp. Never invent anything: every row needs a verbatim quote from the fetched page that contains the outlet name (a list line or sentence naming it).
- Write TSV to {OUT}, header line exactly (tab separated): outlet	domain	kind	url	quote
  domain = bare hostname of the outlet website (repubblica.it); if the page does not give it, use what you know it to be. kind one of: national_daily regional_daily tv wire online_only magazine public_broadcaster radio weekly. url = the fetched page. One row per outlet, no duplicate domains. No tabs/newlines in fields. Write the header line first, then the rows.
- Previous rejection (fix exactly this, empty on first attempt): {REJECTION}
