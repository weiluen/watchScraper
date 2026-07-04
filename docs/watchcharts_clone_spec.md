# Clone specification: a WatchCharts-equivalent product, page by page

Purpose: an executable, auditable spec detailed enough that a junior engineer
(or less-capable model) can build a product that looks and feels nearly
identical to watchcharts.com in **structure, features, data, and behavior**.

Every requirement is numbered (`REQ-…`) so it can be audited line by line.
Companion documents (read them; this spec references them rather than
repeating):
- `docs/watchcharts_build_spec.md` — data model, ingestion, algorithms
- `docs/watchcharts_taxonomy.md` — the 31 filter columns + facet vocabularies
- `docs/pricing_granularity.md` — the pricing atom

**Ground rules (non-negotiable):**
- GR-1: Clone the *structure and function*, not the expression. All copy
  (headlines, blurbs, editorial "Our Take" texts, report prose) must be
  written original. No text may be copied from watchcharts.com.
- GR-2: No WatchCharts logos, brand names, or product images. Watch photos
  come from our own scraped listing images or licensed sources.
- GR-3: Functional labels are fine to match (metric names like "Value
  Retention", column headers, filter names) — those are industry-standard
  descriptors, not protected expression.
- GR-4: Every gated feature must be gated server-side, not just hidden in JS.

Survey provenance: all pages below were visited and structurally inventoried
on 2026-07-04 with a logged-in account, except P5b (brand landing) and P4
(marketplace listing page) which are specified from navigation structure and
standard patterns — marked [PARTIAL SURVEY].

---

## S0 — GLOBAL SHELL (applies to every page)

Layout, top to bottom:
- REQ-S0-1: Promo banner slot (dismissible, campaign text + countdown),
  renders only when a campaign is active.
- REQ-S0-2: Header row: logo (left) · global search box (center) ·
  account avatar menu (right).
- REQ-S0-3: Global search: placeholder shows the live catalog count
  ("Search N watch values…"). Typing ≥2 chars opens an autocomplete
  dropdown of watches (image, brand+nickname+ref, market price) and
  brands/collections; Enter goes to a search results page. Include a camera
  icon inside the search box that deep-links to the photo-ID tool (P13).
- REQ-S0-4: Primary nav row: Home · Dataverse · My Collection · Brands ▾ ·
  Market Research ▾ · For Business ▾ · More ▾ · Premium (highlighted).
  - Brands dropdown: top-10 brand quick links + "View All" → P5a.
  - Market Research dropdown: Market Indexes, Market Reports, Top
    Performers, Price Forecasts, Collecting Ideas, Value Retention,
    Instant Watch Appraisal, Photo ID tool.
  - For Business dropdown: Business Home, Official API.
- REQ-S0-5: Footer: three link groups — Top Brands (brand price pages),
  Top Indexes (index pages), Useful Tools (appraisal, photo ID, apps,
  premium) + legal links.
- REQ-S0-6: Currency selector (modal: pick display currency; persists per
  account; all prices site-wide re-render in the chosen currency using a
  daily FX table; historical charts convert with historical FX and show the
  caveat that exchange rates affect historical trends).
- REQ-S0-7: Auth: email+password and OAuth sign-in; session cookie;
  avatar menu: profile, settings, plan, sign out.
- REQ-S0-8: Every page is server-rendered (SEO) with structured titles:
  "{Thing} | {SiteName}" and per-watch: "{Brand} {Collection} {Nickname}
  {Ref} Price as of {Month Year} | {SiteName}".

Route map (canonical URLs):

| Route | Page |
|---|---|
| `/watches` | P1 catalog home |
| `/dataverse` | P2 full-table dataverse |
| `/watch_model/{id}-{slug}/overview` | P3 watch model page |
| `/listings/watch_model/{id}` | P4 marketplace listings for a watch |
| `/watches/brands` | P5a all-brands index |
| `/watches/{brand-slug}` | P5b brand landing |
| `/watches/indexes` | P6 market indexes |
| `/market` | P7 top performers screener |
| `/market/vr` | P8 value retention by brand |
| `/market/forecast` | P9 price forecast leaderboard |
| `/market/lists` | P10 collecting ideas |
| `/market/reports` | P11 market reports |
| `/appraisal` | P12 instant appraisal |
| `/chronoscope` | P13 photo identification |
| `/portfolios` | P14 collection/portfolios |
| `/subscribe` | P15 plans |
| `/b2b`, `/api` | P16 business + API |

---

## P1 — CATALOG HOME (`/watches`)

The default landing: tagline block, a promo card for the Dataverse, then the
filterable card grid.

- REQ-P1-1: H1 value-prop line + one-sentence subtitle (original copy).
- REQ-P1-2: Dataverse promo card: dark panel, one-line pitch, "Preview"
  CTA + "See plans" CTA, and a live mini-table sample (3 rows: watch,
  sparkline, risk, 1Y%) with a lock note showing the total count.
- REQ-P1-3: Quick-filter row: [Filters ▾] button + per-dimension dropdown
  pills: Brand, Market Price, Retail Price, Case Diameter, Case Material,
  Dial Color. Each pill opens an inline option panel; selections update
  the URL as query params (`?filter_brand=rolex&…`) and re-render
  server-side.
- REQ-P1-4: The [Filters] button opens the full-screen filter modal:
  left column = filter category list grouped under Basic Info / Market
  Performance / Case / Movement (the 31 columns of the taxonomy doc);
  right pane = the selected category's options (chip grid for
  categoricals, dual-slider or min/max inputs for numeric ranges, search
  box for long lists like Brand). Footer: "View {N} Results" button that
  live-updates N as filters change; "Selected (k)" counter; per-section
  Reset.
- REQ-P1-5: Result count line ("{N} results") + Sort dropdown: Relevance,
  Popularity, Price low→high, Price high→low, Random.
- REQ-P1-6: Watch card anatomy (grid, 3-4 per row desktop, image-led):
  production badge (top-right, "In Production" green / "Discontinued"
  neutral) · photo · spec chips row (case material · diameter · WR) ·
  title = Brand + Nickname(bold accent) + Ref · subtitle = collection ·
  price block: "Retail Price {value}·(verified check icon when
  manufacturer-confirmed)" and "Market Price {value}". Whole card links
  to P3.
- REQ-P1-7: Pagination (infinite scroll or numbered; keep URLs shareable
  with `?page=`).

Acceptance: filtering by any dimension changes results server-side; the
URL fully reproduces any filter state; card fields match the API values
displayed on P3 for the same watch.

## P2 — DATAVERSE (`/dataverse`)

A dense, sortable, column-configurable table over the whole catalog
(the "see the entire market" power view). Premium-gated past a preview.

- REQ-P2-1: Same filter system as P1 (shared component).
- REQ-P2-2: Default columns: Watch (image+name+ref) · Chart (1Y
  sparkline) · Risk (score chip) · 1Y % · Market Price · Retail Price.
  Column picker lets users add any of the 31 metric/spec columns.
- REQ-P2-3: Click any column header to sort; server-side sort param.
- REQ-P2-4: Free tier: first ~25 rows visible, the rest blurred behind a
  lock overlay with plan CTA (server returns only the preview rows).
- REQ-P2-5: CSV export button (Professional tier), exports current
  filter+column state.

## P3 — WATCH MODEL PAGE (`/watch_model/{id}-{slug}/overview`)

The core page. Fourteen sections in order; every number visible comes from
the metrics engine (single source of truth = the same API the audit CSVs
read).

- REQ-P3-1 Breadcrumb: Brand › Collection (both link to P5b/P1-filtered).
- REQ-P3-2 Title block: "{Brand} {Collection} {Nickname}" + big
  "Ref. {reference}" line. Buttons: [+ Add to Collection] (opens P14 add
  modal pre-filled), [Buy/Sell] → P4.
- REQ-P3-3 Image column: hero photo, production badge.
- REQ-P3-4 Price box: Retail Price row (info tooltip: from authorized
  dealer; verified check when confirmed; "as of {month}") and Market
  Price row (info tooltip: modeled pre-owned estimate; "as of {date}").
- REQ-P3-5 Condition chips under the price box: "+{x}% in new condition"
  (green outline) and "−{y}% without box/papers" (red outline) — the two
  hedonic multipliers applied to this watch's estimate.
- REQ-P3-6 Region tabs: Global · America · Europe · Asia — switch the
  price + chart to region-fit estimates.
- REQ-P3-7 Price History chart: smooth estimate line + shaded volatility
  band; window tabs 3M/6M/1Y/2Y/5Y/Max (5Y and Max behind premium lock
  icons); crosshair tooltip (date + value); [Download] link (CSV of
  date,price,volatility — premium).
- REQ-P3-8 Charts & Metrics tab strip: Listings · Volume · Days on
  Market · Auctions.
  - Listings: scatter of individual listings, red=Sold blue=Unsold,
    source toggle chips ("{OurMarketplace} (n)" / "eBay (n)"), "Show N"
    selector. Points link to the listing.
  - Volume: monthly sold-count bars.
  - Days on Market: distribution of listing durations.
  - Auctions: realized auction results list.
- REQ-P3-9 Metric tiles (6): Market Volatility % · Risk Score /100 ·
  Value Retention % · Market Inception (Mon YYYY) · 1Y Sales Volume ·
  Median Days on Market. Each with an info tooltip stating its
  definition.
- REQ-P3-10 Risk Score section: score /100 + band label + five component
  sub-scores displayed as x/4 (Short Term Performance, Long Term
  Performance, Liquidity, Predictability) and x/3 (Value Retention).
- REQ-P3-11 Price Forecast section: 1-year, three scenarios (optimistic /
  reasonable / conservative, each a % and implied price). Premium-gated:
  free users see a lock + sample link.
- REQ-P3-12 Rankings: percentile rows vs two peer groups ("All {Brand}",
  "All {Brand} {Collection}"): Market price, 1Y performance, Market
  volatility, Value retention, Risk score, 1Y sales volume, Days on
  market, Market tenure — rendered "Top N%" / "Bottom N%".
- REQ-P3-13 Instant Appraisal inline widget: three dropdowns (Watch
  Condition; Delivery Contents = watch only / with box / with papers /
  full set; Region) + [Get Estimate] → estimate = market price × the
  hedonic multipliers. Same engine as P12.
- REQ-P3-14 For Sale: live active listings for this watch (our
  marketplace section + "Right now on eBay" section): thumbnail, seller,
  buy-now badge, title, price, country; paginated "Page 1 of N".
- REQ-P3-15 "Our Take" editorial block: 2-4 original paragraphs on the
  reference's history and variant lineage (hand-written or LLM-drafted +
  human-reviewed; NEVER copied).
- REQ-P3-16 Related Watches carousel: same-collection and successor/
  predecessor refs with "{price} MKT" captions.
- REQ-P3-17 Model Specifications table (three groups: Basic Info / Case /
  Movement — all fields of the taxonomy doc); every categorical value is
  a link to P1 pre-filtered to that value.

## P4 — MARKETPLACE LISTINGS (`/listings/watch_model/{id}`) [PARTIAL SURVEY]

- REQ-P4-1: All active listings for one watch: filter by condition,
  completeness, region, price; sort by price/newest.
- REQ-P4-2: Listing rows: photo, title, condition, completeness, price
  vs market-price delta chip ("3% below market"), seller, region.
- REQ-P4-3: If running a first-party marketplace: listing creation flow,
  offers, escrow — OUT OF SCOPE v1; link out to source listings instead.

## P5a — BRANDS INDEX (`/watches/brands`)

- REQ-P5a-1: Alphabetical grid of all brand names (text links), ~100+
  brands, each → P5b.

## P5b — BRAND LANDING (`/watches/{brand}`) [PARTIAL SURVEY]

- REQ-P5b-1: Brand header + brand market index chart (level, 1Y%).
- REQ-P5b-2: Collection tiles (Submariner, Datejust, …) → P1 filtered.
- REQ-P5b-3: Top models by popularity (card row), brand stats (median
  price, 1Y trend, total models tracked).

## P6 — MARKET INDEXES (`/watches/indexes`)

- REQ-P6-1: Index taxonomy, four kinds: Overall Market · Brand indexes ·
  Group indexes (e.g. sports/dress segments) · Price-Range indexes
  (e.g. under-5k, 5-10k…). Sub-nav tabs for each kind.
- REQ-P6-2: Top strip: brand index mini-cards (level + 1Y% chip),
  horizontally scrollable.
- REQ-P6-3: Featured Indexes: 2 large cards (Overall, top brand) with
  level, 1Y absolute + % change, window tabs (3M…Max), full chart.
- REQ-P6-4: "All Indexes" list grouped by kind: name, level, 1Y% chip,
  each → its own index detail page (same layout as featured card, full
  width, plus constituents note).
- REQ-P6-5: Methodology link → original explainer page.
- REQ-P6-6: Index math (from build spec): chain volume-weighted median
  trend returns of constituent watches — composition-safe; rebase each
  index to a fixed base date. Level is denominated in USD-ish points
  (e.g. an average constituent price) so absolute changes read naturally.

## P7 — TOP PERFORMERS (`/market`)

- REQ-P7-1: A screener form: Brand multi-select (all brands) · minimum
  Market Price dropdown · minimum trend % dropdown · window dropdown
  (3M/6M/1Y/…') · [Find Watches].
- REQ-P7-2: Results table: rank · Name (image, brand+nickname+ref,
  production badge) · Market Price · {window} Price Trend %. Sortable,
  paginated, each row → P3.
- REQ-P7-3: Default view (no query): top gainers over 1Y above $1,000.

## P8 — VALUE RETENTION (`/market/vr`)

- REQ-P8-1: Original explainer: retention = premium/discount of
  IN-PRODUCTION watches vs retail; why it matters. USD note.
- REQ-P8-2: Brand leaderboard: for each covered brand, big % (median
  retention across its in-production watches), signed & colored, with
  "{n} in-production watches" subtitle. Sorted descending.
- REQ-P8-3: Each brand row expands (or links) to its best/worst retention
  models table (Name, Retail, Market, Retention %).
- REQ-P8-4: Computation: per watch retention = market/retail − 1
  (in-production only); brand figure = median across its watches;
  refresh nightly.

## P9 — PRICE FORECASTS (`/market/forecast`)

- REQ-P9-1: Leaderboard of all forecastable watches ("Showing 25 of N"):
  Name · Market Price · Reasonable Forecast % · Past Sales (1Y). Sorted
  by past sales by default.
- REQ-P9-2: Free users see the forecast column masked ("+XX.X%") with an
  upgrade CTA; paid tier sees values. MASKING HAPPENS SERVER-SIDE.
- REQ-P9-3: Row → P3 forecast section.

## P10 — COLLECTING IDEAS (`/market/lists`)

Curated algorithmic screens, each a card → a list page. Launch set (rules
are exact, over the metrics store):
- REQ-P10-1 "Trading above retail": in-production AND retention > 0.
- REQ-P10-2 "Steady gainers": positive trend in ≥4 of the last 5 years
  (or monotone smoothed 5Y trend where history is shorter).
- REQ-P10-3 "Comeback watches": 2Y trend < 0 AND 6M trend > 0.
- REQ-P10-4 "Resilient sports watches": style=Dive/Racing/Pilot AND 1Y
  trend above the overall-index 1Y trend.
- REQ-P10-5: Each list page: intro (original copy), the screen's rule
  stated plainly, results table (Name, Market Price, the relevant
  metrics), refreshed nightly.

## P11 — MARKET REPORTS (`/market/reports`)

- REQ-P11-1: Reverse-chronological report cards (cover, title, date,
  summary) → report detail pages (long-form original analysis with
  embedded index/metric charts). Quarterly cadence. Optionally gated.

## P12 — INSTANT APPRAISAL (`/appraisal`)

- REQ-P12-1: H1 ("How much is my watch worth?"-equivalent, original) +
  watch search box (same autocomplete as global search).
- REQ-P12-2: After picking a watch: three dropdowns — Watch Condition
  (New/Unworn · Excellent · Good · Fair) · Delivery Contents (Watch only
  · With box · With papers · Full set) · Region — then [Get Your
  Estimate].
- REQ-P12-3: Result: estimate value + range, computed as market price ×
  condition multiplier × completeness multiplier (region-fit base).
  Show the watch's P3 link. Log the appraisal event.
- REQ-P12-4: Social-proof strip: "recently appraised" watches with
  counts (from the appraisal event log).
- REQ-P12-5: Free, but rate-limited by captcha after N anonymous uses.

## P13 — PHOTO IDENTIFICATION (`/chronoscope`)

- REQ-P13-1: Landing page: hero (photo → identified instantly), 3-step
  how-it-works, [Try It Now] + app links.
- REQ-P13-2: The tool: upload/camera capture → image embedding model →
  nearest-neighbor search over per-watch reference-image embeddings →
  top-k candidates with confidence; each result card shows watch +
  market price + link to P3.
- REQ-P13-3: v1 implementation: CLIP-class embedding of catalog images,
  cosine search (FAISS); log corrections to improve.

## P14 — MY COLLECTION (`/portfolios`)

- REQ-P14-1: Multi-portfolio: tab bar "My Collection (n)" · "My Wishlist
  (n)" · [New Collection]. Wishlist = a portfolio without purchase data.
- REQ-P14-2: Header: total value hero + {window}% and $ change chips +
  window tabs (3M/6M/1Y/2Y/Max) + [Download] (CSV of holdings +
  history) + value-over-time chart (sum of holdings' value series).
  FX caveat line + "prices last updated {date}".
- REQ-P14-3: Cost Basis stat row: NUMBER OF WATCHES · TOTAL COST · TOTAL
  MARKET VALUE · GAIN/LOSS $ · GAIN/LOSS % — computed only over holdings
  that have both a market price and a purchase price (state this).
- REQ-P14-4: Holdings table: Watch (image, name, ref, variant) · Market
  Price · Purchased (price + date) · Gain/Loss ($ and %, colored) ·
  row menu (edit, move to other portfolio, delete).
- REQ-P14-5: [Add Watch] modal: watch search → variant picker (dial) →
  condition, completeness, purchase price, purchase date, notes.
  Valuation of the holding applies its condition/completeness hedonics.
- REQ-P14-6: Price alerts: per watch, threshold + direction → email.

## P15 — PLANS (`/subscribe`)

- REQ-P15-1: Two product tracks side by side: "Website & App" and "API
  Access". Billing toggle Monthly/Annually (+savings), promo-code
  support with countdown.
- REQ-P15-2: Website tiers (names ours; structure equivalent):
  - Free: current prices, 1Y history, collection tracking, dataverse
    preview.
  - Tier 2 (~$199/yr class): full history, forecasts, downloads,
    dataverse full, alerts.
  - Tier 3 (pro): CSV exports, bulk tools, priority data.
  API tiers: Level 1 / Level 2 by call volume + fields; free trial CTA.
- REQ-P15-3: "Compare Plans & Features" matrix table; every gated feature
  in this spec references a tier here. Stripe billing; grandfathering
  supported (existing plan shown with switch options).

## P16 — BUSINESS + API (`/b2b`, `/api`)

- REQ-P16-1: B2B landing: use-cases (dealers, insurers, lenders),
  contact/sales form.
- REQ-P16-2: API: docs page + key management; REST endpoints (below);
  metered by tier.

---

## S1 — API CONTRACTS (JSON; the UI consumes ONLY these)

| Endpoint | Returns |
|---|---|
| `GET /api/search?q=` | autocomplete: watches (id, name, ref, price, thumb), brands, collections |
| `GET /api/watches?filters…&sort&page` | catalog cards / dataverse rows |
| `GET /api/watch/{id}` | everything on P3: prices, condition multipliers, spec sheet, metrics, risk components, rankings, forecast (tier-gated fields), related |
| `GET /api/watch/{id}/history?region&window` | [{date, price, volatility}] |
| `GET /api/watch/{id}/listings?status=sold|active&source` | scatter/For-Sale rows |
| `GET /api/indexes` · `GET /api/index/{slug}` | index list / series |
| `GET /api/market/top?brand&min_price&min_trend&window` | screener results |
| `GET /api/market/vr` | brand retention leaderboard |
| `GET /api/market/forecasts?page` | forecast leaderboard (masked per tier) |
| `GET /api/lists/{slug}` | collecting-ideas list results |
| `POST /api/appraise` | {watch_id, condition, contents, region} → estimate |
| `POST /api/identify` | image → top-k watch candidates |
| CRUD `/api/portfolios`, `/api/portfolios/{id}/items`, `/api/alerts` | collection |

Gating matrix (server-enforced): forecast values, >1Y history, downloads,
dataverse full table, CSV export → paid tiers per P15.

---

## S2 — WHAT ALREADY EXISTS IN THIS REPO (execution = close the gaps)

Already built (verify, don't rebuild): catalog w/ variants+specs+nicknames;
scrapers (eBay-sold via browser harvest, Chrono24 asks); tiered matcher;
cleaning (junk/fake-anchor/outlier); hierarchical valuation w/ hedonics,
bands, material/size atoms; metrics (retention, volatility, risk composite,
volume, 3-scenario forecast); active-listing DOM tracking; smooth index;
pages: catalog+refs explorer w/ filters, model page (value chart, metrics,
variants matrix, spec sheet, sales, appraisal-ish verdict), portfolio,
buying guide; audit CSV exports.

Gap list, in build order for the executor:
1. Global shell: search autocomplete (REQ-S0-3), currency selector
   (REQ-S0-6), auth/accounts (REQ-S0-7). Definition of done: search
   returns watches by ref/nickname/name in <150ms; currency persists.
2. P3 completions: region tabs (fit valuation per region — requires
   region on listings; parse from source/site country), Listings scatter
   sold/unsold toggle, Volume + DOM + Auctions tabs, Rankings section
   (peer percentiles exist in metrics.py — surface them), Related
   carousel, per-value spec links.
3. P6 index pages (index kinds: overall/brand/group/price-range; the
   engine's chained-trend index generalizes — parameterize the
   constituent filter).
4. P7 screener, P8 VR leaderboard, P9 forecast leaderboard w/ masking,
   P10 four screens (rules above; all are queries over metrics).
5. P14 upgrades: multi-portfolio + wishlist, holding condition/
   completeness fields (hedonic-adjusted marks), CSV download, alerts.
6. P2 dataverse table + column picker + preview gating; P15 plans +
   Stripe; P12 standalone appraisal page (engine exists — add condition
   multiplier estimation for condition levels, currently only full-set);
   P13 photo ID (CLIP+FAISS); P5b brand pages; P11 reports (editorial).
7. Each step ships with: tests (pytest), an audit CSV where a number is
   produced, and a line-item check against this spec's REQ ids.

Estimated sequencing for a junior executor: steps 1-2 first (they touch
existing code), then 3-4 (pure queries over existing metrics), then 5-7.
