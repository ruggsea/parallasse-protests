# PLAN: how Italian and other media covered youth protests, 2026-09-25 to 2026-10-25

Question: is Italian coverage of youth protests more hostile than coverage elsewhere (violence-focused, delegitimising)?
If Italy is no worse, the report says so. Each commitment is fixed here before the labelling runs.

## Constants (checked against analysis/constants.py and the data by analysis/check_plan.py)
```
WINDOW = 2026-09-25 .. 2026-10-25
GATE1_CHARS = 1500
LABEL_CHARS = 1500
PAYWALL_MIN_CHARS = 1500
SERVED_WINDOW = 65536
MAX_TOKENS_A = 900
MAX_TOKENS_B = 3000
TEMPERATURE = 0
MIN_BODY_CHARS = 200
LIVE_BLOG_CHARS = 30000
CLAUDE_SAMPLE_ITALIAN = 200
CLAUDE_SAMPLE_OTHER = 100
CLAUDE_SAMPLE_SEED = 20261030
KAPPA_SAMPLE_ITALIAN = 300
KAPPA_SAMPLE_OTHER = 300
KAPPA_SAMPLE_SEED = 20261031
RELEVANCE_ROWS_GATE1 = 110771
RELEVANCE_ROWS_GATE2 = 9269
FRAMING_ARTICLES = 18355
DUP_HEAD_CHARS = 600
```

## Stages 5 and 6 as run
- Relevance (stage 5): keyword gate 1 (110,771 unique candidate URLs of 1,400,288 articles), gate 2 (9,269 unique URLs), Qwen3.8-27B labels protest and youth. Measured: precision protest 73/80, youth 33/40 (stratified n=120); recall of both gates 199/200 (n=200, 1 missed, Infobae Mexico).
- Framing (stage 6): articles with protest=1 and youth=1. Model A Qwen3.8-27B BF16 labels all of them (two calls: title only; title+full text). Model B gpt-oss-120b (as released, MXFP4) labels a kappa sample. One fixed prompt per call kind, temperature 0, no other sampling setting. Text is cut only if the prompt would pass the served window; every cut is counted.
- Fields: stance toward protesters, stance toward demands, protest type, share of sentences on violence and on demands, quoted roles, delegitimising terms copied from the article, headline stance and headline frame.
- Body-level results use only articles whose text is not paywall_truncated and not shorter than MIN_BODY_CHARS; headline-level results use all articles. Live blogs (over LIVE_BLOG_CHARS) are flagged and shown separately.

## Result shapes (decided before the run)
1. Bar per country: share hostile (body), with n, Italy highlighted. Same with share of sentences on violence vs demands.
2. Table Italy vs pooled others vs each country: hostile share, violence share, police-quoted share, delegitimising-term rate, each with n and a bootstrap interval over outlets.
3. By outlet leaning within Italy and within others.
4. Weekly line, Italy vs others.
5. Agreement table: model A vs model B (Cohen's kappa per field, n), model A vs Claude-read sample.
6. Log-odds keyword table (informative prior) per country group.

## Input audit (research-process.md, 2026-10-25), 2026-10-30
1. Fields of data/articles/*.jsonl: url (key), listed_date (not sent), status (only 200 used), tries (not sent), title (sent, both calls), date (used for time series, not sent), text (sent in the body call; not sent in the head call). Outlet country is sent (country of the outlet, from data/ledger.tsv). Leaning and URL are NOT sent. The outlet name is removed from titles when it is a trailing ' - Name' / ' | Name' found on 20+ titles of that outlet (same rule for all outlets); body text can still carry agency credits (e.g. © ANSA), named in limitations. date is used to keep only articles inside the window (134 outside were dropped).
2. Rendered prompts read end to end: 75 (25 Italy, 40 other countries, 5 longest, 5 shortest) by three Sonnet readers (tmp/audit_read0-2.txt). Findings and fates: title repeated as first body line (fixed: removed when equal to, or contained in, the title, same rule for all outlets; auditor found 7.8% of non-Italian vs 2.0% of Italian had it); site-name suffix in title (left; harmless); promo and related-article blocks in text (left, shared by all countries; named in limitations); live blogs (68 over 30,000 chars; flagged); empty bodies (ctvnews-ca stub "Published:"; articles under 200 chars get no body call; title-only call still runs); articles sharing their first 600 characters with another article of the same outlet (stored live-blog text, cookie walls) get no body call; machine-summary header lines (Resumen IA, Gerando resumo, Key Points) dropped; wrong-page texts (1tv-ru, tanjug-rs, CNews/Europe1 blurbs) are NOT detected and go in limitations; off-topic items (known from precision, 91%).
3. Same bytes and tokens on every lane: both models read the same prompt text; token counts use each model own tokenizer; the two models run on different engines by design (cross-model check).
4. Window: both engines serve 65,536 tokens (Qwen3.8-27B supports 262,144; the shared engine is capped at 65,536). Measured on all articles by the auditor: longest 32,151 tokens, 0 cut. Every row stores prompt_tokens and cut; the full count goes in the methods box.
5. Smoke test: analysis/smoke_framing.py (fails on empty or short body, empty title, unfilled placeholder, over-window; selftest shows three known-bad records caught).
6. Constants checked: analysis/check_plan.py.
7. Outside reader: opus-auditor, 2026-10-30, verdict QUALIFIED; its items and fates: protest_country field added (event vs coverage: analysis splits domestic and foreign coverage); hostile example without violence; outlet suffix and title-repeat rules made uniform; duplicate-body skip; date window applied; failed calls retried; paywall flag applied in analysis from mark_paywall.is_truncated (ANSA loses 63% of bodies to it; reported).
