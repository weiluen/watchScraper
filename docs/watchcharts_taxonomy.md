# WatchCharts data model (reverse-engineered from watchcharts.com/watches)

Captured 2026-07-04 from the filter schema embedded in page source. Their
listing is server-rendered; the facet definitions ship as JSON in the HTML.
29,657 individual watches (each a reference+variant), each fully categorized.

## The 31 filter columns and their backing data fields

Every watch is an object with these fields. `specs.*` are physical
attributes; the rest are computed market metrics.

| Filter | Backing field | Kind |
|---|---|---|
| Brand | `brand` | categorical |
| Collection | `collection_name` | categorical (e.g. "Submariner Date") |
| Market Price | `price_formatted` | computed estimate |
| Retail Price | `retail.value_formatted` | catalog |
| In Production | `in_production_timestamp` | status |
| Market Inception | `market_first_date` | date first traded |
| Style | `specs.Basic Info.Style` | categorical |
| Complications | `specs.Basic Info.Complications` | multi-value |
| Features | `specs.Basic Info.Features` | multi-value |
| Case Diameter | `specs.Case.Case Diameter` | numeric mm |
| Case Thickness | `specs.Case.Case Thickness` | numeric mm |
| Case Material | `specs.Case.Case Material` | categorical |
| Bezel Material | `specs.Case.Bezel Material` | categorical |
| Dial Color | `specs.Case.Dial Color` | categorical |
| Dial Numerals | `specs.Case.Dial Numerals` | categorical |
| Lug Width | `specs.Case.Lug Width` | numeric mm |
| Water Resistance | `specs.Case.Water Resistance` | numeric M |
| Crystal | `specs.Case.Crystal` | categorical |
| Movement Type | `specs.Movement.Movement Type` | categorical |
| Number of Jewels | `specs.Movement.Number of Jewels` | numeric |
| Power Reserve | `specs.Movement.Power Reserve` | numeric hours |
| Frequency | `specs.Movement.Frequency` | numeric bph |
| 3M/6M/1Y/2Y/5Y Price Trend | (computed) | % change |
| Price Forecast | `forecast.scenarios.reasonable.percent_change` | scenario model |
| Value Retention | `value_retention` | market/retail ratio |
| Risk Score | `risk_score` | 0–100 volatility index |
| 1Y Sales Volume | `popularity` | transaction count |
| Median Days on Market | `dom.median` | liquidity |

Key structural facts:
- **Forecast is SCENARIO-based** (`forecast.scenarios.reasonable.percent_change`)
  — they carry multiple scenarios (reasonable / others), not a point estimate.
- **Days on Market** (`dom.median`) is a first-class liquidity metric — needs
  listing appearance + disappearance timestamps, i.e. tracking listings over time.
- **Market Inception** (`market_first_date`) — the date a reference first traded,
  used to bound trend windows.
- **Popularity = 1Y sales volume** — transaction count, their liquidity/demand proxy.

## Facet option values (the categorical vocabularies)

### Style (watch archetype)
Dive, Field, Pilot, Dress, Digital, Racing

### Production Status
In Production, Discontinued

### Case / Bezel Material
Steel, Rose gold, Yellow gold, Red gold, White gold, Gold/steel, Platinum,
Palladium, Titanium, Ceramic, Carbon, Aluminum, Bronze, Tantalum, Tungsten,
Plastic, Rubber, Silver, Gem-set, Gold-plated

### Dial Color
Black, Silver, White, Blue, Grey, Green, Brown, Champagne, Gold, Pink, Red,
Yellow, Purple, Orange, Bordeaux, Turquoise, Mother of pearl, Meteorite,
Skeletonized, Transparent, Silver (solid), Gold (solid), Bronze

### Dial Numerals
No numerals, Arabic numerals, Roman numerals, Lines, Gemstones

### Crystal
Sapphire crystal, Mineral glass, Plexiglass, Glass, Plastic

### Movement Type
Automatic, Manual winding, Quartz, Solar, Smartwatch

### Number of Jewels
21, 23, 24, 25, 27, 31, … (numeric range)

### Power Reserve
38, 42, 48, 50, 72, 80 hours, … (numeric range)

### Frequency
18000, 19800, 21600, 25200, 28800, 36000 bph

### Case Diameter / Thickness / Water Resistance / Lug Width
Numeric range facets (39–44mm diameter, 9–14mm thickness, 30–300M WR).

### Complications (multi-value)
Date, Chronograph, Weekday, GMT, Moon phase, Tachymeter, Month,
Perpetual calendar, Annual calendar, 4-year calendar, Alarm, Flyback,
Tourbillon, Year, Panorama date, Minute repeater, Double chronograph,
Jumping hour, Equation of time, Chiming clock, World time

### Features (multi-value)
Luminous hands/indices/numerals, Display back, Central seconds,
Screw-down crown, Screw-down push-buttons, Chronometer, Master chronometer,
Rotating bezel, Small seconds, Limited edition, Special edition,
Gemstones and/or diamonds, Quick set, Power reserve display, PVD/DLC coating,
Solar watch, Skeletonized, Tempered blue hands, Guilloché dial, Helium valve,
Crown left, Genevian seal, Vintage, Smartwatch, One-hand watches

## Naming convention (the identity model)

Each watch card: `{Brand} {Nickname?} {Reference}` / `{Collection}`
e.g. "Rolex Starbucks 126610LV" / "Submariner Date"
- Brand + Reference is the unique key
- Nickname is a display adornment (never the identity)
- Collection is the family grouping
- Card chips show: Case Material · Case Diameter · Water Resistance
- Card prices: Retail Price (with a "verified" check) + Market Price (estimate)
- Production badge: "In Production" / "Discontinued"

## Per-watch metric algorithms (reverse-engineered from the model page)

Example: Rolex Starbucks 126610LV — Market $14,395 / Retail $11,900.
Chart = smooth "pre-owned price estimate" line + shaded band; the band is a
**per-timepoint volatility envelope** (page JSON: `{price, volatility}` pairs,
volatility ≈ 0.07). Evidence below = individual listings, **Sold (red) vs
Unsold (blue)**, aggregated from **WatchCharts + eBay** (100 each here).

### Price estimate & condition
- **Market Price** = modeled pre-owned estimate (their words), a smoothed
  central value — NOT a raw median. Matches our hierarchical smoother.
- **Condition adjustments** (hedonic multipliers on the estimate):
  `+4.0% in new condition`, `-1.9% without box/papers`. Displayed as toggles.
- **Regional estimates**: Global / America / Europe / Asia.

### The six headline metrics
1. **Market Volatility** (4.4%) = std of recent price returns of the estimate.
2. **Risk Score** (69/100, "High Risk") = "short-term depreciation risk when
   buying on the secondary market." COMPOSITE of five sub-scores:
   - Short Term Performance (1/4)
   - Long Term Performance (0/4)
   - Liquidity (1/4)
   - Predictability (2/4)  ← inverse volatility / fit quality
   - Value Retention (3/3)
   Higher = riskier. (This watch is falling short-term, illiquid-ranked, but
   retains value long-term.)
3. **Value Retention** (+21.0%) = market / retail − 1.
   CONFIRMED: 14,395 / 11,900 − 1 = +21.0% exactly.
4. **Market Inception** (Sep 2020) = first date the reference traded.
5. **1Y Sales Volume** (3,676) = count of transactions, trailing year (demand).
6. **Median Days on Market** (19.0) = median (delist − list) days over sold
   listings. REQUIRES tracking each listing's appearance + disappearance.

### Forecast — 3-scenario fan (not a point estimate)
Page JSON `forecast.scenarios`:
- optimistic  +12.1%
- reasonable   +3.9%   ← the headline
- conservative −4.3%
Horizon = 1 year.

### Peer-percentile Rankings
Each watch is ranked within peer groups (All Rolex, All Rolex Submariner):
Market price, 1Y performance, Market volatility, Value retention, Risk score,
1Y sales volume, Days on market, Market tenure — each shown as Top/Bottom N%.

---

## Gap analysis vs our engine

Already built: smooth value + band, full-set hedonic, reference/dial/material
hierarchy, damped forecast, ask/sold spread (round-trip cost).

To match WatchCharts, add (in order of data-feasibility with what we scrape):
- **Value Retention** = market/retail − 1 (we have the inputs) ✓ easy
- **Market Volatility** = std of smoothed-value weekly returns ✓ easy
- **Risk Score** composite (short/long perf, liquidity, predictability,
  retention) ✓ from existing series
- **1Y Sales Volume** = clean sold count per watch ✓ have it
- **3-scenario forecast** (optimistic/reasonable/conservative) — widen our
  damped trend into a fan ✓ easy
- **Condition toggles** (new / without box&papers) — extend hedonics ✓
- **Peer-percentile rankings** — rank within brand/family ✓
- **Median Days on Market** — REQUIRES scraping unsold/active listings and
  tracking list→delist. New scraper capability (Chrono24 active listings).
- **Full spec dimensions** (Style, Complications, Features, Movement details) —
  catalog enrichment; useful for filtering, not pricing.
