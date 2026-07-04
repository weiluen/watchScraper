# Sales Motion — Complications. (watch market intelligence)

The product: per-reference price tracking, valuation, risk metrics, and forecasts
for luxury watches, built on cleaned eBay-sold + Chrono24-ask data. Each
reference (down to dial/material variant) is its own tracked market — the same
atomic unit WatchCharts monetizes.

## Who buys (ICP, in order of willingness to pay)

1. **The collector-investor** (2–10 watches, $30k–$500k at risk). Wants: "what
   is my collection worth this week, and is the watch I'm about to buy going to
   lose me money?" Converts on: portfolio mark-to-market, round-trip cost,
   value-retention rankings, price alerts.
2. **The first big purchase buyer** ($5k–$15k, 3–6 month research cycle). Wants
   confidence, not analytics. Converts on: buying guide, "vs retail" framing,
   days-on-market (can I get it at AD?). Mostly free tier — the funnel's top.
3. **Grey-market dealers / flippers** (10–100 transactions/yr). Want: spread
   detection (region arbitrage: eBay US sold vs Chrono24 EU ask), DOM by
   reference, volume. Converts on: API/CSV export, screener, forecasts.
   This is the Professional tier ($299).
4. **B2B later**: insurers (agreed-value policies need marks), lenders
   (collateral valuation), estate appraisers. Sell reports/API, not seats.

## How they find us (acquisition)

- **Programmatic SEO is the whole game** — the WatchCharts playbook. Every
  reference page targets "«ref» price" / "«nickname» price" queries
  ("126610LN price", "John Mayer Daytona value"). 137 priced pages today;
  the moat compounds as the corpus grows. Requirements already shipped:
  unique per-ref content (value, chart, specs, rankings), fast pages,
  clean URLs, breadcrumbs.
- **Weekly market report** (email + blog): top movers, index level, one
  collecting idea. The report is the retention loop AND link-bait.
- **Community presence**: answer valuation questions on r/Watches,
  r/Watchexchange, WatchUSeek with chart links (not ads).
- **YouTube/watch-media partnerships**: reviewers cite our charts on screen
  (attribution → brand). Free data licensing for creators in exchange for
  credit.

## Free → paid (conversion levers, all already implemented)

| Lever | Free | Paid |
|---|---|---|
| Price history | 1Y | 5Y / Max |
| Forecasts | masked leaderboard ("+XX.X%") | full 3-scenario fan |
| Chart download | — | CSV export |
| Portfolio | 3 holdings | unlimited + alerts + CSV |
| Screener/Dataverse | top rows | full table + filters |

Gate server-side (done — forecasts mask at the API). The masked forecast
leaderboard is the single highest-intent upsell surface: the user has already
asked "what's going up?"

## Pricing (shipped on /subscribe)

- **Basic $0** — the SEO surface and the funnel.
- **Enthusiast $99/yr** — the collector-investor. Anchor tier; target 80% of
  paid revenue. Annual-only keeps churn structural, not monthly-decisional.
- **Professional $299/yr** — dealers: API, exports, full screener. Low volume,
  high margin, nearly zero marginal cost.

## Retention

- Weekly "your collection: $X (+Y%)" email — the product markets itself every
  week the user owns watches.
- Price alerts (shipped): "126610LN crossed $15k" pulls dormant users back.
- Quarterly "state of the watch market" for paid tiers.

## Sequencing (next 3 moves)

1. Grow the corpus: more references priced → more SEO pages → more free users.
   Data breadth IS distribution.
2. Turn on the weekly email (portfolio mark + top movers). Requires accounts.
3. Stripe on /subscribe, gate 5Y/Max + forecast fan behind Enthusiast.
