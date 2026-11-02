# Parallasse: visual and editorial style guide

Written 2026-10-25 for the protest-coverage report. Source: the 18 pieces under the Parallasse tag on scomodo.org, read in full through the WordPress REST API (`/wp-json/wp/v2/posts?slug=...`, allowed by robots.txt: `Disallow:` empty) and the HTML pages. Fetches through `scrapers/polite_fetch.py`; 71 images saved in `design/examples/` (named `p<N>_<original file>`, N = row number below), downloaded with curl at 1 request per second, all from URLs found in those pages.

## What Parallasse is (and a correction to the brief)

Parallasse is the "rassegna stampa critica" (critical press review) of Scomodo: media criticism, not general data journalism. Weekly pieces (Dec 2022 - Oct 2023, ~400-1,000 words) became a newsletter in Sept 2024 (every Tuesday). The text says "Ogni mese raccontiamo con dati, interviste e analisi, un fenomeno strutturale del giornalismo italiano." Most pieces have no charts: they are text plus screenshots of front pages, headlines and tweets. Real charts appear in the monthly "mensile" format; the one found is the Gaza piece (row 8). So the chart style below rests on ONE piece with three charts, plus the logo/banner system seen in all 18. Treat chart rules as strong for that piece and inferred for anything beyond.

## Pieces studied (18, all Italian)

All URLs `https://scomodo.org/<slug>/`. Charts column: "none" means no chart, only screenshots. Text length from the API (words).

| # | Date | Title | Slug | Words | Visuals |
|---|---|---|---|---|---|
| 1 | 2023-05-12 | ChatGPT e intelligenza artificiale: un'occasione per restaurare il legame di fiducia tra giornali e lettori | chatgpt-e-intelligenza-artificiale-unoccasione-per-restaurare-il-legame-di-fiducia-tra-giornali-e-lettori | 703 | none; headline/article screenshots, brain illustration |
| 2 | 2023-10-02 | Dietro l'ampia copertura de Il Messaggero per la nuova linea di tram a Roma si celano gli interessi del suo editore Caltagirone | dietro-lampia-copertura-de-il-messaggero-per-la-nuova-linea-di-tram-a-roma-si-celano-gli-interessi-del-suo-editore-caltagirone | 858 | none; headline screenshots, "50 articoli in meno di 2 mesi" count in a screenshot card |
| 3 | 2025-04-28 | Editoriale n. 65 (Scomodo, not Parallasse proper; tagged) | editoriale-n-65 | 306 | photos only; excluded from style evidence |
| 4 | 2023-09-26 | I casi di Rubiales, Mendy e Portanova raccontano il problema della narrazione degli abusi sessuali nel mondo del calcio | i-casi-di-rubiales-mendy-e-portanova-raccontano-il-problema-della-narrazione-degli-abusi-sessuali-nel-mondo-del-calcio | 932 | none; 10 headline screenshots in a carousel, a red quote card |
| 5 | 2023-05-13 | I giornali italiani hanno un problema con il giornalismo investigativo | i-giornali-italiani-hanno-un-problema-con-il-giornalismo-investigativo | 973 | none; 11 page/tweet screenshots (one shows a network diagram taken from the newspaper) |
| 6 | 2023-07-31 | I lanzichenecchi sul treno Roma-Foggia. Ovvero del potere degli Elkann sui giornali italiani | i-lanzichenecchi-sul-treno-roma-foggia-ovvero-del-potere-degli-elkann-sui-giornali-italiani | 869 | none; page screenshots |
| 7 | 2022-12-14 | Il caso Juventus visto dal gruppo GEDI è una celebrazione dei successi degli Agnelli | il-caso-juventus-visto-dal-gruppo-gedi-e-una-celebrazione-dei-successi-degli-agnelli | 641 | none; one logo image |
| 8 | 2024-04-15 | Il problema del giornalismo italiano nella copertura di Gaza | il-problema-del-giornalismo-italiano-nella-copertura-di-gaza | 1,850 | 3 charts: grouped bars, 2 daily line charts (the data piece) |
| 9 | 2023-07-03 | I quotidiani italiani si dividono sul caso Santanchè | i-quotidiani-italiani-si-dividono-sul-caso-santanche | 743 | none; screenshots |
| 10 | 2023-06-07 | La narrazione dei femminicidi sui quotidiani italiani è declinata al singolare maschile | la-narrazione-dei-femminicidi-sui-quotidiani-italiani-e-declinata-al-singolare-maschile | 687 | none; one image |
| 11 | 2023-06-02 | La nuova anima de L'Unità divide il panorama giornalistico italiano | la-nuova-anima-de-lunita-divide-il-panorama-giornalistico-italiano | 734 | none; screenshots |
| 12 | 2023-07-16 | La Verità abbraccia la causa del negazionismo climatico | la-verita-abbraccia-la-causa-del-negazionismo-climatico | 668 | one pasted survey table (green header, grey rows, from an outside source), page screenshot |
| 13 | 2022-12-19 | Lirio Abbate non è più direttore de L'Espresso: un altro caso in cui gli interessi degli editori minano l'indipendenza di un giornale | lirio-abbate-non-e-piu-direttore-de-lespresso-un-altro-caso-in-cui-gli-interessi-degli-editori-minano-lindipendenza-di-un-giornale | 382 | none; screenshots |
| 14 | 2023-05-19 | Matteo Renzi alla direzione de Il Riformista rivela il suo uso personalistico del giornalismo | matteo-renzi-alla-direzione-de-il-riformista-rivela-il-suo-uso-personalistico-del-giornalismo | 533 | none; screenshots |
| 15 | 2023-06-26 | Morte, ricordo ed eredità di Silvio Berlusconi sui giornali italiani e internazionali | morte-ricordo-ed-eredita-di-silvio-berlusconi-sui-giornali-italiani-e-internazionali | 819 | none; a wall of front pages (Italian, UK, US, FR, ES) |
| 16 | 2024-09-07 | Parallasse, la nostra rassegna stampa critica settimanale, diventa una newsletter | parallasse-diventa-una-newsletter | 599 | none; the manifesto text |
| 17 | 2023-09-18 | Preservare l'indipendenza di una redazione dai cambi di direzione: cosa può insegnare la vicenda del Journal du Dimanche | preservare-lindipendenza-di-una-redazione-dai-cambi-di-direzione-cosa-puo-insegnare-la-vicenda-del-settimanale-francese-journal-du-dimanche | 963 | none; French and Italian page screenshots |
| 18 | 2023-07-24 | I giornali italiani potrebbero imparare dalle nuove "firme" del New York Times | una-riflessione-sul-problematico-rapporto-di-fiducia-tra-stampa-italiana-e-lettori-dallultima-iniziativa-del-new-york-times | 594 | none; screenshots |

Rows 1, 2, 6-11, 13-15, 17, 18 are weekly text pieces; 4 and 8 are the longer monthly-style pieces. Row 8 is the only chart source. Because the weekly format has no charts, Parallasse's "visual language" for charts = row 8 and its three PNGs.

## Row 8 in detail (the reference piece)

`https://scomodo.org/il-problema-del-giornalismo-italiano-nella-copertura-di-gaza/`, 15 Apr 2024 (modified 23 Apr). Authors Luca Bagnariol, Beatrice Chartroux, Angela Perego; data collection, processing and machine-learning classification credited by name (including Ruggero Marino Lazzaroni); column curated by Andrea Carcuro and Luca Bagnariol. Data: about 17,800 articles from la Repubblica, Libero and Corriere della Sera, 7 Oct 2023 to 25 Feb 2024, collected by keyword (Israele, Palestina, antisemitismo, islamofobia and derivatives). Method followed The Intercept (Johnson and Ali, 9 Jan 2024) on US papers.

Three charts, each a square 1920x1920 PNG (`design/examples/p8_PARALLASSE-MENSILE-N54_WEB-01/02/03.png`; N54 = issue 54):
1. **Grouped vertical bars**: number of headlines containing Israele / Hamas / Palestina, per newspaper (x: REPUBBLICA, CORRIERE DELLA SERA, LIBERO; y: 0-2000 in steps of 250). Bars have fully rounded tops; no data labels on bars; legend as big bold labels with a coloured dot to their right, bottom right.
2. **Daily line chart with dots**, 3-day moving average, articles per day mentioning Palestina/Israele in the body, three papers, Oct to Feb. One line per paper; one paper (Corriere) is drawn thick, outlined, with white-centred dots, the other two thin. Legend bottom, spread over one row.
3. **Two-series daily line chart**: antisemitismo (red) against islamofobia (black), Oct to Mar, in a thin red frame. The point is made by the gap, not by an annotation.

Text around the charts: the caption is a plain full sentence placed in the body text directly above the chart ("Numero di articoli pubblicati ogni giorno che contengono le parole ... raggruppati per giornale. I dati sono riportati in media mobile di tre giorni."). The chart image itself has no title, no subtitle, no source line and no annotations. Sources are in the prose (The Intercept named and dated; method in the paragraph before; a footnote with an asterisk on limits: titles only, not bodies; language-model labels held back "per cautela" because of opacity of the models). The key number is stated in the text: "852 articoli con antisemitismo ... solo 34 islamofobia. È un rapporto di venticinque a uno."

## Palette (hex, sampled with PIL from the Gaza chart PNGs and the banner)

| Role | Hex | Evidence |
|---|---|---|
| Background (chart canvas) | `#EEE7D7` | 193,025 to 210,250 of 230,400 pixels in each of the three charts |
| Background (banner, torn-paper) | `#EAE4D7` | banner, with paper texture and torn edges |
| Main red (series 1, labels, axis month names, thin frame) | `#C1443F` | bars, dots, legend text in all three charts |
| Light salmon (series 2) | `#DB9D87` | Palestina bars, Libero line |
| Pale tint (hover/frame, rare) | `#E3C1AF` / `#E8D4C3` | antialiasing and thin tints |
| Black (series, contrasting series only) | `#000000` | islamofobia line in chart 3 |
| Axis numbers | near black (`#000000`-`#1a1a1a`, light weight) | visible in charts |
| Gridlines and frame | grey-mauve, about `#B8AEB0` (read by eye, not sampled) | thin horizontal rules |
| Open series | no fill, 1 px red outline on the cream | Israele bars, Corriere dots |
| Logo brand red | `#D23737` | "//" in the logo (banner) |
| Logo dark | `#323232` | PARA and ASSE letters |

Scomodo site accents (theme CSS, `style.min.css` v2.6.1): `#F5A405` (orange, 8 uses), `#FF0200` (red), `#DE1C6F` (pink). These are the magazine colours, not used in the Parallasse charts. The weekly pieces use screenshots with no palette of their own.

Principle seen in the charts: ONE hue (red) in three tints plus an outline-only third state, on warm cream; a black second hue only when two series are opposed. Categories are told apart by fill (solid / tint / outline), not by different hues.

## Typefaces

- **Charts**: a DIN-style sans (condensed look). Axis numbers light/regular, category names, months and legend in DIN Bold, all caps, in the series red. Identified by eye from the PNGs.
- **Scomodo site CSS**: `din`, `din-bold`, `din-black`, a custom `scomodo` font, and `EB Garamond` (serif) for body text (stylesheet `style.min.css`). Elementor also loads Roboto and Roboto Slab by default.
- **Logo**: Helvetica/Arial-style bold grotesque, all caps, tight, "PARA//ASSE" with the two slashes in red.
- **Free fallbacks (Google Fonts)**: DIN Bold labels -> `Barlow Condensed` 600/700 (closest) or `Oswald`; axis numbers -> `Barlow Semi Condensed` 300/400; body -> `EB Garamond`; logo -> `Inter Tight` 700 or system `Arial Bold`. Use ONE family for the chart (Barlow Condensed) and weights to separate roles.

## Chart grammar

1. Canvas `#EEE7D7`, no card, no drop shadow, no gradient. Square (1:1) export 1920x1920 for sharing; keep generous top margin (the charts leave 10-20% empty above).
2. Bars: vertical, grouped, fully rounded top corners, no gap between bars of the same group, gap between groups. One bar in each group is outline-only. Y axis: plain numbers every 250 (or round step), thin grey gridlines, a 0 baseline; x labels in red bold caps, two lines when long ("CORRIERE / DELLA SERA").
3. Lines: thin (1-2 px at 1920), a dot on every data point, plain straight segments between dots, 3-day moving average disclosed in the caption. Y numbers left, no axis title. X axis only shows month names in red bold caps (OTT NOV DIC GEN FEB MAR) with small ticks. Frame optional, thin red.
4. Highlight one series by line weight and an outlined double-stroke marker, others thin.
5. Legend: big bold caps label + filled/outline dot, set apart at the bottom or bottom right, not inside the plot. Series names are written in the series colour.
6. No data labels on bars, no value annotations, no arrows, no callout boxes. The numeric point goes in the prose.
7. No unit on the axis in the image; unit and period are in the caption sentence.

The three most characteristic chart types: (1) grouped rounded-top bars with an outline-only "reference" bar, (2) daily dotted lines with one series emphasised by thickness (3-day moving average), (3) two-series dotted line pair where the contrast (red vs black) carries the argument.

## Titles, captions, sources, text

- **Title**: a full declarative sentence that states the finding or accusation, long (10-25 words), e.g. "Il problema del giornalismo italiano nella copertura di Gaza"; "Dietro l'ampia copertura de Il Messaggero per la nuova linea di tram a Roma si celano gli interessi del suo editore Caltagirone". No question marks, no puns. Sentence case.
- **Subtitle**: one to three sentences of summary under the title (visible on the tag page: "Una ricerca di Scomodo per cercare di capire l'esistenza e l'estensione di un bias pro-Israele su tre giornali...").
- **Caption**: a plain sentence in the body text above the figure: what is counted ("Numero di articoli ... che contengono ..."), grouping, smoothing. Period at the end.
- **Source and method**: in prose and a footnote with an asterisk, never printed on the image. Credits block at the end lists authors, data collection, processing, classification, curators.
- **Language and tone**: Italian; analytical, sober, critical of owners and editors ("interessi dell'editore", "uso personalistico"); every claim is tied to a named newspaper and often a quoted headline in «guillemets». Experts quoted by name with their role. Admits limits ("prendere questi dati con particolare cautela"). First person plural "noi di Scomodo" in the intro and method.
- **Length**: weekly 380-1,000 words; monthly data piece about 1,850 words with 3 charts; newsletter manifesto 600 words.
- **Evidence by screenshot**: the weekly pieces show the actual headline, front page or tweet (with the paper's own typography, visible masthead) as the proof. A comparison of "how paper A and paper B said it" is the core move. This is Parallasse's own visual language; our report should reuse it for headline examples.

## Logo and branding

- Wordmark **PARA//ASSE**: bold caps grotesque, dark `#323232`, with the double slash `//` in red `#D23737` replacing the double L ("PARALLASSE"). Placed centred on a cream torn-paper banner (`BANNER-parallasse*.png`, 1920x1200; same banner reused for each piece, in 13+ versions). The slashes can stand as a separator motif.
- Section label "Questo articolo parla di" with tags; byline "di <author>" and date under the title.
- Parent brand: Scomodo logo top left (separate, lowercase wordmark). Parallasse charts carry no logo on the image in the one sample.
- The slides in the carousel for row 4 use a red card (`~#B22A2A`, read by eye) for quote cards with white serif title and sans body, so red-on-cream and white-on-red are both in the system.

## What to avoid (to look like Parallasse, and by contrast with what they do not do)

- No multi-hue categorical palettes, no blue/green/purple: red tints plus black only.
- No chart titles, source lines or watermarks inside the image; no 3D, no gradients, no shadows, no gridline clutter beyond thin horizontals.
- No decorative icons or emoji; no stock illustration inside charts.
- No data labels on every bar, no callout arrows: if a number matters, write it in the sentence.
- No white background (cream always); no sentence-case legend (caps only); no tiny legend text.
- Do not change the logo colours or spacing.
- Do not give the report an unsourced number: the house standard is every claim attached to a named paper, with the method stated and the limits admitted.

## What could not be reached

- **Instagram** (`instagram.com/scomodo/`): refused by robots.txt through the fetcher; not accessed. Scomodo's carousels there probably show the same cards, but unseen.
- **Newsletter issues after Sept 2024** (Tuesday emails): no public archive found; `scomodo.org/newsletter/` only shows the sign-up description (Parallasse "arriva tutti i martedì"). Platform unknown. No newsletter pieces studied beyond the announcement (row 16).
- **Substack**: `parallasse.substack.com` exists but belongs to someone else (GIScience); `scomodo.substack.com` 404. Neither used.
- **Monthly charts other than row 8**: the tag page lists 18 posts, only one has data charts. No other chart piece found, so every "chart rule" rests on three images from one issue (N54). The fonts are identified by eye (DIN), not from a font file inside the PNGs.
- Grey gridline hex and the red quote-card hex in row 4 were read by eye from the displayed images, not sampled. Palette values in the table marked as sampled come from PIL pixel counts.
- Page text of the 2022-23 weekly pieces is not in the page HTML; it was read from the REST API JSON (`/tmp` copies only; not saved in the repo).

## Defaults for our report (derived, to apply)

Canvas `#EEE7D7`; main `#C1443F`; secondary `#DB9D87`; contrast `#000000`; text/dark `#323232`; logo accent `#D23737`; font Barlow Condensed (labels, bold caps) and Barlow Semi Condensed (numbers); body EB Garamond. Italy in the main red, other countries in the salmon tint or outline, pooled-others in outline; use black only for an opposed pair. Captions as one sentence above the figure stating what is counted, n, period and smoothing; method and limits in a footnote; credits block listing who collected, processed and classified.
