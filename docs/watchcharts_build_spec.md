# How to build WatchCharts, from scratch — a complete engineering spec

This document describes the entire WatchCharts product in enough detail that a
competent beginner could rebuild it. It is written from a line-by-line,
page-by-page survey of watchcharts.com (2026-07-04). Read it top to bottom;
later sections depend on earlier ones.

WatchCharts is, in one sentence: **a market-data platform that tracks ~29,657
individual watch models, estimates each one's pre-owned market value from
aggregated listings, and surfaces per-watch analytics (trends, risk,
liquidity, forecasts) plus a collector portfolio tool.**

The product is four layers stacked on one data model:

1. **Ingestion** — scrape/import listings from marketplaces (eBay + their own
   marketplace + auctions), normalize each to a specific watch reference.
2. **Estimation** — turn noisy per-listing prices into one smooth market value
   per watch, per region, per condition.
3. **Metrics** — derive trend, volatility, risk, liquidity, forecast, rankings.
4. **Presentation** — the website: search/filter table, per-watch pages,
   portfolio, market research, appraisal, API.

---

## PART 0 — The two atomic concepts

Everything hinges on two ideas. Get these wrong and nothing else works.

### 0.1 A "watch" is a reference number, optionally a dial/material variant

The unit of everything — pricing, charts, metrics — is one specific
manufactured configuration, identified by its **reference number** (e.g.
`126610LV`). Where one reference is sold with materially different dials or
materials that trade at different prices, each becomes its own watch
(`116508 Green` vs `116508 Champagne`). A **nickname** ("Starbucks", "John
Mayer") is a display label that can be ambiguous and must never be the pricing
key. A **collection/family** ("Submariner Date") groups references.

Identity key: `(brand, reference_number, dial_variant?)`.

### 0.2 Every sale is a noisy observation of a latent value

You never see "the price." You see individual transactions, each perturbed by
condition, completeness (box/papers), seller, region, and timing. The whole
estimation layer exists to recover the latent value curve from this noise.

---

## PART 1 — THE DATA MODEL

Build these tables first. (Postgres assumed.)

### 1.1 `brands`
`id, name, slug`. ~50 brands (Rolex, Patek, AP, Omega, Cartier, Tudor, …).

### 1.2 `watches` — the core catalog (one row per atomic watch)
Identity: `id, brand_id, reference_number, dial_variant (nullable),
collection/family, model_name`.

Production: `production_start_year, production_end_year (null=current),
market_first_date (first ever traded), retail_price_usd`.

**Full spec sheet** — WatchCharts categorizes every watch on these exact
dimensions (their filter vocabulary; store each as its own column):

- Basic Info: `style` (Dive/Field/Pilot/Dress/Digital/Racing),
  `complications[]` (Date, Chronograph, GMT, Moon phase, Perpetual calendar,
  Annual calendar, Tourbillon, Minute repeater, …), `features[]` (Rotating
  bezel, Luminous hands/indices/numerals, Screw-down crown, Chronometer,
  Master chronometer, Helium valve, Display back, Small seconds, Limited
  edition, …).
- Case: `case_diameter_mm, case_thickness_mm, case_material, bezel_material,
  dial_color, dial_numerals` (No numerals/Arabic/Roman/Lines/Gemstones),
  `crystal` (Sapphire/Mineral/Plexiglass/Glass), `lug_width_mm,
  water_resistance_m, bracelet`.
- Movement: `movement_type` (Automatic/Manual/Quartz/Solar/Smartwatch),
  `movement_caliber, frequency_bph, jewels, power_reserve_hours`.

Material vocabulary (case & bezel): Steel, Rose/Yellow/Red/White gold,
Gold/steel (two-tone), Platinum, Palladium, Titanium, Ceramic, Carbon,
Aluminum, Bronze, Tantalum, Tungsten, Plastic, Rubber, Silver, Gem-set,
Gold-plated.

Dial colors: Black, Silver, White, Blue, Grey, Green, Brown, Champagne, Gold,
Pink, Red, Yellow, Purple, Orange, Bordeaux, Turquoise, Mother of pearl,
Meteorite, Skeletonized, Transparent.

### 1.3 `watch_nicknames`
`id, watch_id, nickname`. Many-to-many: one nickname ("Batman") can point at
several references (generations); one watch can have several nicknames. NEVER
unique per nickname. Used for search and display only.

### 1.4 `watch_aliases`
`id, watch_id, alias`. Alternate 1:1 reference spellings (long-form AP refs,
Patek dash suffixes `5711/1A-014`). These DO pin identity, including the dial.

### 1.5 `listings` — raw scraped transactions & asks (the evidence)
One row per observed listing: `id, source_id, external_id (unique per source),
watch_id (resolved, nullable), title (raw), price_usd, price_type
(sold|asking|auction), condition, has_box, has_papers, region
(America/Europe/Asia), listing_url, first_seen, last_seen, sold_at/observed_at,
delisted_at, raw_json`.

- `sold` rows = completed transactions (from eBay sold, auctions, their
  marketplace sales).
- `asking` rows = active listings (dealers, marketplace) — tracked over time.
- Match provenance: `match_method, match_confidence, parsed_year,
  parsed_attributes` (see Part 3).

### 1.6 `active_listings` (or a view over `listings`)
The subset with `delisted_at IS NULL` for days-on-market and supply counts.
Each scrape upserts `last_seen`; a listing missing from the latest scrape gets
`delisted_at` stamped and `days_on_market = delisted_at − first_seen`.

### 1.7 `price_history` / `price_snapshots`
Per watch, per region, per week (or day): `watch_id, region, date, price
(the estimate), volatility, n_sold, n_listed`. This is the time series behind
every chart. (WatchCharts stores per-timepoint `{price, volatility}` pairs.)

### 1.8 `metrics` (materialized, recomputed nightly)
Per watch: `value_retention, market_volatility, risk_score,
risk_components{}, sales_volume_1y, median_days_on_market, market_inception,
forecast_scenarios{optimistic,reasonable,conservative}, price_trend_3m/6m/1y/2y/5y`.

### 1.9 `rankings` (materialized)
Per watch, per peer-group (all-brand, all-collection): percentile of each
metric.

### 1.10 `sources`
`id, name (ebay, marketplace, auction_house_X), base_url, is_active`.

### 1.11 Collector tables
`users, collections, collection_items(watch_id, purchase_price, purchase_date,
condition), watchlists, price_alerts(watch_id, threshold, direction)`.

---

## PART 2 — DATA INGESTION (the hardest, most important layer)

The prediction engine is only as good as the data. WatchCharts aggregates
**eBay + their own marketplace + auction results**. Build scrapers per source.

### 2.1 eBay (sold + active)
- Sold/completed listings give real transaction prices with sale dates. URL
  pattern: `ebay.com/sch/i.html?_nkw={query}&LH_Sold=1&LH_Complete=1&...`.
- Active "Buy It Now" listings give the asking side and feed days-on-market.
- eBay blocks server-side scraping aggressively (403). Options, cheapest
  first: (a) a real logged-in browser session driving fetch() from the page
  context; (b) residential-proxy rotation; (c) the official eBay Browse/
  Marketplace-Insights APIs (paid, cleanest). WatchCharts almost certainly
  uses APIs + partnerships at scale.
- Parse per card: title, price, sold-date, condition text, item id, image.

### 2.2 Their own marketplace
WatchCharts runs a marketplace ("Buy/Sell"), which gives them first-party
sold + active data no competitor has. If rebuilding, substitute Chrono24
(dealer asks; use TLS-impersonation/`curl_cffi` to pass Cloudflare) and any
marketplace you can partner with.

### 2.3 Auction houses
Scrape/import realized auction results (Christie's, Phillips, Sotheby's,
Bonhams, online auctions). These anchor the high end and vintage.

### 2.4 The scrape loop (run continuously)
For each source × query (brand/collection sweeps):
1. Fetch pages, parse listings.
2. Deduplicate by `(source, external_id)`.
3. Resolve each to a `watch_id` (Part 3).
4. Insert `sold` rows; upsert `asking` rows into `active_listings` (bump
   `last_seen`).
5. Reconcile: asks not seen this run → `delisted_at` stamped (presumed sold),
   compute `days_on_market`.
6. Record a `scrape_run` for observability.

Cadence: high-liquidity refs daily; long tail weekly. Store everything; the
time series is the asset.

---

## PART 3 — MATCHING (listing → specific watch): the rules engine

A listing title is free text ("2020 Rolex Daytona 116508 John Mayer Green
Dial 18ct YG B&P"). You must resolve it to exactly one `watch_id` or leave it
unresolved. This determines data quality more than anything else.

### 3.1 Attribute extraction (run on every title, at scrape time)
Regex out: reference-number candidates (per-brand patterns), year (4-digit,
1950–now; latest plausible wins), size (`\d{2}(\.\d)?mm`), dial color
(`… dial`), bezel, material class (two-tone/precious/steel/titanium/ceramic),
bracelet (jubilee/oyster/oysterflex/rubber/…), full-set/box-papers flag,
no-date flag. Store as `parsed_attributes` JSON + `parsed_year`.

### 3.2 The tiered matcher (ordered; first hit wins), with confidence
1. **exact_ref (0.95)** — a catalog reference appears in the title. If the
   title's year is outside the reference's production window, downgrade to
   0.80 but keep the ref (sellers mistype years, not ref numbers). For a
   multi-dial reference, resolve the dial via a variant nickname in the title
   ("John Mayer" → Green, 0.95), the parsed dial term with per-ref synonyms
   ("gold dial" on a YG Daytona = Champagne, 0.92), or a Patek dash suffix
   alias. If the dial is unknown, park on the reference parent bucket (0.85)
   — identified but NOT priced as a variant.
2. **alias (0.90)** — a 1:1 alternate spelling (dash suffix pins the dial).
3. **attributes (0.65)** — no ref: the collection + parsed
   size/material/dial/bezel/date/year must narrow the collection's catalog to
   exactly one reference.
4. **nickname (≤0.60)** — a community name resolves to a family and a likely
   watch, but capped BELOW the pricing threshold: nicknames are ambiguous
   marketing labels and must never tie a sale to a price point.
5. **family-only (0.30)** — only the collection is known; stays unpriced at
   the watch level.

**Pricing threshold: only sales with match_confidence ≥ 0.65 AND a resolved
reference price a specific watch.** Everything else informs the family trend
only.

### 3.3 Anti-patterns to encode (learned the hard way)
- A nickname must never cross brands ("panda dial" on an Omega ≠ Rolex Daytona
  Panda).
- A year outside every candidate generation refuses the match (a 1969 "Pepsi"
  is ref 1675, not the modern 126710BLRO).
- Aftermarket mods are junk: "custom dial", "redial", "iced out", "diamond
  set/added" → exclude entirely (they poison genuine variant prices).

---

## PART 4 — DATA CLEANING (before any statistic)

Raw matched sales are still contaminated. Flag, never delete; every exclusion
carries a reason.

1. **Junk filter** — parts/accessories/bundles: "box only", "papers only",
   straps, bezels, links, "for parts", winders, MoonSwatch, aftermarket mods.
2. **Cross-source anchor (fakes)** — a "sold" far below an independent anchor
   (dealer-ask median for the same watch+material, or retail) is presumed
   counterfeit/parts. Halo models (Nautilus, Aquanaut) have fake-dominated
   eBay pools at self-consistent price points — only a cross-source anchor
   catches them. Rule: sold < 35% of the (watch, material) ask anchor → drop.
3. **Robust outlier trim** — within (watch, material), a modified z-score
   (median absolute deviation) beyond ~3.5 is an outlier. Run this AFTER the
   fake filter, or fakes drag the median and flag genuine sales.

Clean rate lands ~75%. Keep the flags queryable for auditing.

---

## PART 5 — THE VALUATION ENGINE (noisy sales → one smooth value)

This is the "Market Price" number and the chart line. **Never plot weekly
medians of whichever watches sold that week — that is composition noise, and
forecasting it is forecasting nothing.** WatchCharts' chart is a smooth
estimate line with a volatility band; sold/unsold listings are scattered
underneath as evidence.

### 5.1 The model
`log(price) = node_offset + family_trend(t) + config_effects + noise`

- **Node** = the watch identity (variant → reference → family+material
  generic). Its **offset** (premium over the family base) is stable and
  estimable from few sales. This is how a 3-sale variant gets a trustworthy
  value: it borrows the family's trend and carries only its own level offset.
- **Family trend(t)** = a kernel-weighted (Gaussian, ~21-day bandwidth)
  **median** smoother over ALL the family's sales after subtracting each
  sale's node offset. Median → one bad listing can't bend the line. Smoother →
  no weekly sawtooth. Composition-adjusted → a mix shift can't masquerade as a
  price move.
- **Config effects** = hedonic multipliers estimated from within-node
  contrasts and pooled globally: full-set/box-and-papers (~+10–14%), bracelet
  type, condition (new vs used ~+4%). Standardize every sale to a reference
  configuration (full set, good condition) before fitting; re-apply a
  holding's own config when valuing it.

### 5.2 Fitting (iterate to convergence, ~3 passes)
1. Initialize node offsets = unshrunk node medians (fixed-effects; shrinking
   here leaks composition into the trend).
2. Trend = smoother over (offset-adjusted sales).
3. Re-estimate each offset = median residual (sale − trend).
4. Repeat.
5. For **reporting**, shrink offsets empirical-Bayes toward the parent
   (variant → reference → family), `κ = n/(n+K)`, so thin nodes lean on their
   parent instead of their own noise. A 3-sale John Mayer's prior is "a gold
   Daytona 116508", not "a Daytona".

### 5.3 Bands and stratification
- **Band** = per-timepoint volatility envelope: at each grid point, the
  smoother's local residual scale → ±1.96·SE band. This is WatchCharts'
  shaded region.
- **Material stratification** — compute family trends within (family,
  material) strata; a two-tone-heavy week is a mix shift, not appreciation.
  Use each family's dominant stratum for the headline trend.
- **Regional** — repeat the fit per region (America/Europe/Asia) for the
  regional toggle; Global is the pooled fit.
- **Grid clamping** — start the trend grid at ~the 5th-percentile sale date so
  one vintage sale can't stretch a flat pseudo-history.

### 5.4 Condition & completeness toggles (the "+4% new / −1.9% no papers")
Store the hedonic multipliers; the UI toggles apply them to the base
estimate. The Instant Appraisal form is exactly this: pick condition +
delivery contents + region → estimate = base × condition_mult ×
completeness_mult × region_mult.

---

## PART 6 — THE METRIC ALGORITHMS (each headline number)

All computed off the smoothed value series and the clean sold corpus.

### 6.1 Market Price
Latest point of the smoothed value series (standard config, chosen region).

### 6.2 Value Retention = market / retail − 1
Confirmed exactly on WatchCharts ($14,395 / $11,900 = +21.0%). Only meaningful
where retail is known.

### 6.3 Price Trends (3M/6M/1Y/2Y/5Y)
% change of the smoothed value between now and t−window. Measured on the
SMOOTH line, not raw prices.

### 6.4 Market Volatility
Std of the smoothed value's recent (weekly) log-returns, shown as a small %
(e.g. 4.4%). Feeds the band and the risk score.

### 6.5 Risk Score /100 — "short-term depreciation risk", higher = riskier
Composite of five sub-scores (each 0–1), weighted, ×100:
- **Short-Term Performance** — recent (1–3M) price direction (falling = risky).
- **Long-Term Performance** — 1–2Y direction.
- **Liquidity** — sales volume / days-on-market (illiquid = risky).
- **Predictability** — inverse of volatility / smoother fit quality.
- **Value Retention** — market vs retail (trading below retail = risky).
Display the component breakdown and a band label (Low/Moderate/High).

### 6.6 1Y Sales Volume (a.k.a. Popularity)
Count of clean sold transactions in the trailing year. Demand proxy.

### 6.7 Median Days on Market
Median of `(delisted_at − first_seen)` over sold/delisted asking listings.
REQUIRES longitudinal listing tracking (Part 2.4 step 5). Until listings have
actually delisted, report active-listing count as the available supply signal.

### 6.8 Market Inception
First observed sale/listing date for the reference.

### 6.9 Price Forecast — 3-scenario fan (1-year horizon)
Extrapolate the smoothed trend's recent slope, **heavily damped** (~0.4×;
grey-market drift is slow, wiggles must not extrapolate). Widen into three
scenarios by the volatility band:
- reasonable = damped-slope projection
- optimistic = reasonable + vol·√horizon
- conservative = reasonable − vol·√horizon
(WatchCharts showed +12.1 / +3.9 / −4.3%.) Premium-gated on their site.

### 6.10 Rankings (peer percentiles)
For each metric, rank a watch within peer groups (all-brand, all-collection):
"Top 44%", "Bottom 26%". Recompute nightly across the catalog.

---

## PART 7 — THE WEBSITE (page by page, feature by feature)

### 7.1 Global nav
Home · Dataverse · My Collection · Brands ▾ · Market Research ▾ · For Business
▾ · Premium. Plus a global search box with **photo search** (Chronoscope —
upload a watch photo, image-match to a reference).

### 7.2 Dataverse — the filterable catalog (their `/watches`)
A table/grid over all ~29,657 watches. Every column in Part 1.2 is a filter
AND a sort. Left "Filters" mega-panel groups: Basic Info (Brand, Market Price,
Retail Price, Production Status, Style, Complications, Features, Market
Inception), Market Performance (3M/6M/1Y/2Y/5Y trend, Forecast, Value
Retention, Risk Score, 1Y Sales Volume, Median Days on Market), Case (all case
specs), Movement (all movement specs). Cards show image, brand+nickname+ref,
collection, spec chips (material·diameter·WR), Retail + Market price,
production badge, mini price sparkline + risk + 1Y%. Sort by Relevance,
Popularity, Price, Brand, etc. Server-render for SEO; the facet schema ships
in the page.

### 7.3 The per-watch model page (the heart of the product)
URL: `/watch_model/{id}-{slug}/overview`. Sections top to bottom:

1. **Header** — Brand › Collection breadcrumb, "Ref. {number}", Add to
   Collection + Buy/Sell buttons.
2. **Image + production badge** ("Current Production Model" / "Discontinued").
3. **Price box** — Retail Price (with verified check) and Market Price ("Our
   pre-owned price estimate", dated). Condition chips: "+X% in new condition",
   "−Y% without box/papers". Regional tabs: Global / America / Europe / Asia.
4. **Price History chart** — smooth estimate line + volatility band; time
   windows 3M/6M/1Y/2Y/5Y/Max; **Download** (CSV of the series). Tooltip
   crosshair reads the value at any date.
5. **Charts & Metrics** — sub-tabs:
   - *Listings* — scatter of individual listings, **Sold (red) vs Unsold
     (blue)**, source toggle **WatchCharts / eBay**, show-N control.
   - *Volume* — sales volume over time (histogram).
   - *Days on Market* — distribution/trend of listing durations.
   - *Auctions* — auction results.
6. **Metric tiles** — Market Volatility, Risk Score, Value Retention, Market
   Inception, 1Y Sales Volume, Median Days on Market.
7. **Risk Score** — the /100 with band label and the five-component breakdown.
8. **Price Forecast** — 3-scenario fan (premium-gated).
9. **Rankings** — percentile bars vs All-{Brand} and All-{Collection}.
10. **Instant Appraisal** — form (Watch Condition, Delivery Contents, Region)
    → Get Estimate (applies the hedonic multipliers of Part 5.4).
11. **For Sale** — live listings right now (eBay + marketplace), price + region
    + seller, paginated.
12. **Our Take** — editorial writeup: history, variant lineage, context.
13. **Related Watches** — similar references with their market prices.
14. **Model Specifications** — the full spec sheet (Part 1.2), three columns:
    Basic Info / Case / Movement.

### 7.4 My Collection (portfolio)
Add watches (by reference + dial + condition + purchase price/date). Shows:
total collection value (marked to each watch's estimate, adjusted for the
holding's condition/completeness), cost basis, gain/loss, value-over-time
chart, allocation by brand/family, per-holding P&L. Watchlists + price alerts.

### 7.5 Brands
Per-brand landing: brand-level index, top models, aggregate stats, model list.

### 7.6 Market Research
- **Market Indexes** — aggregate indices (overall, per-brand), the "see the
  whole market" chart. Build by chaining volume-weighted median trend returns
  across watches (composition-safe).
- **Market Reports** — periodic editorial + data reports (quarterly market
  state).
- **Top Performers** — leaderboards by trend/appreciation.
- **Price Forecasts** — forecast leaderboard.
- **Collecting Ideas** — curated buy lists (screens: dip + liquidity +
  retention).
- **Value Retention** — retention leaderboard.
- **Instant Watch Appraisal** — the standalone appraisal tool.
- **Chronoscope** — photo → watch identification (image embedding search).

### 7.7 For Business
- **Business Home** — B2B pitch (dealers, insurers).
- **Official API** — programmatic access to prices/metrics. Build as a REST
  API over the `metrics` + `price_history` tables with keys + rate limits.

### 7.8 Membership tiers
Free (basic prices), Premium/Insider (forecasts, downloads, full history),
Professional (API, bulk). Gate the premium metrics server-side.

---

## PART 8 — BUILD ORDER (do it in this sequence)

**Phase 1 — Catalog & identity.** Build `brands`, `watches` (with full specs),
`nicknames`, `aliases`. Seed a few hundred references by hand + spec sheets.
Without a clean catalog, matching is impossible.

**Phase 2 — Ingestion + matching.** One source (eBay sold) end to end: scrape
→ extract attributes → tiered matcher → `listings`. Get the match right;
audit with a CSV of every sale + its assignment. Add a second source (dealer
asks) for the cross-source anchor.

**Phase 3 — Cleaning + valuation.** Junk/fake/outlier flags, then the
hierarchical smoother with hedonics. Output one smooth value + band per watch.
This is the product's core IP.

**Phase 4 — Metrics.** Value retention, trends, volatility, risk score,
volume, forecast fan. Materialize nightly. Add days-on-market once listing
tracking has run long enough to see delistings.

**Phase 5 — Website.** Dataverse table (server-rendered facets) → per-watch
model page (chart + metrics + specs) → portfolio → market research → appraisal
→ API. Charts: smooth line + band + evidence scatter; never raw medians.

**Phase 6 — Scale & moat.** More sources (auctions, your own marketplace),
more references (toward 29k), photo search, editorial, memberships. The moat is
proprietary transaction data + time — the longer the history, the better the
trends and the harder to replicate.

---

## PART 9 — THE THINGS THAT WILL BITE YOU (hard-won)

1. **Composition drift** is the #1 statistical trap. Weekly medians move
   because the *mix* of what sold changed, not prices. Stratify + smooth
   offset-adjusted sales. Our own index read +9% raw vs −6% composition-
   adjusted over the same weeks — the +9% was mix, not appreciation.
2. **Fakes look real.** Counterfeit halo models trade at self-consistent
   prices; within-source stats can't catch them. Need cross-source anchors.
3. **Nicknames are ambiguous.** Never price on a nickname.
4. **Dial/material moves price as much as the model.** A 116508 green trades
   ~65% above champagne. Variants must be separate watches.
5. **Sparse data needs shrinkage.** Don't give a 3-sale watch its own trend;
   borrow the family's and carry only the offset.
6. **Don't forecast noise.** Damp the trend hard; grey-market drift is slow.
7. **eBay/Cloudflare block scrapers.** Budget for APIs, proxies, or a real
   browser session. Ingestion is the unglamorous 80% of the work.
8. **Days-on-market needs longitudinal data.** You can't compute it from one
   snapshot — track listings appearing and disappearing over weeks.
