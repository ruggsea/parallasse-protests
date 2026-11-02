# Task spec: outlets and political leaning for a list of countries

Study: how news media of many countries covered youth protests (2026-09-25..2026-10-25). For each country in YOUR LIST do two things, in this order.

## A. Outlets: data/outlets/<slug>.tsv   (slug = lowercase country name with underscores, e.g. united_kingdom)
10 to 20 main news outlets of the country across the political spectrum (national dailies, regional papers with national reach, TV news, wire agency, online-only outlets, news weeklies, public broadcaster, radio). Prefer outlets with their own website that publishes in the country's language. Header line exactly (tab separated): `outlet domain kind url quote`
- domain = bare hostname of the outlet site (repubblica.it). kind one of national_daily regional_daily tv wire online_only magazine public_broadcaster radio weekly.
- url = a page you fetched through the fetcher (HTTP 200). quote = a sentence/line of at least 20 characters copied EXACTLY from that page's cached text (data/fetchcache/<sha256(url)[:24]>.json, field text; raw HTML, so a quote cannot span tags) containing the outlet name. Good evidence pages: Wikipedia 'Media of X', 'List of newspapers in X', the outlet's own Wikipedia article, Reuters Institute Digital News Report country page, the other-language Wikipedia.
- One row per outlet, unique domains. Check: `python3 grids/outlets/check_outlets.py data/outlets/<slug>.tsv x` must print nothing (exit 0). Domains come from your knowledge; verify the homepage answers via the fetcher (`python3 scrapers/polite_fetch.py https://domain/ --head 300`) and drop or fix outlets whose site does not answer.

## B. Political leaning: data/leaning/<slug>.tsv
One row per outlet of A, same order and strings. Header exactly: `outlet domain leaning url1 quote1 url2 quote2 note`. leaning in: far_left left centre_left centre centre_right right far_right unclassified. Two different fetched source pages per classified outlet (Wikipedia article political position / editorial line; Media Bias/Fact Check; AllSides; Reuters Institute DNR audience placement; Media Pluralism Monitor; academic studies; local-language Wikipedia), quote at least 20 characters copied exactly from that page's cached text supporting the leaning. Where the sources disagree write `DISAGREEMENT: ...` in note and pick what the more specific source supports. Use `unclassified` with a note saying why when sources give no left-right placement (do not guess). Check: `python3 scrapers/check_leaning.py data/leaning/<slug>.tsv` must print nothing.

## Rules
- Fetch pages ONLY with `python3 scrapers/polite_fetch.py URL [--head N]` (robots-aware, cached, logged). Never curl/wget. Skip pages it refuses. Never kill processes by name. Never invent a URL or quote. Use your own uniquely named helper scripts in a subfolder of your scratchpad. Do not edit other files. WebSearch budget is shared and limited: prefer Wikipedia and direct URLs, use search only to find a missing page.
- Report per country: outlet count, leaning counts (classified / unclassified), both check outputs verbatim, and any weak spots.
