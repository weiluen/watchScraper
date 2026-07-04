"""Market-research services (spec pages P6-P10).

Everything here is a query over the already-computed MarketSnapshot: the
valuation model (family trends, per-node values/forecasts), the family
signals, and the priced references. No new data or models — the research
suite is a set of views over the same single source of truth the watch pages
use, so every number reconciles.
"""

import numpy as np
import pandas as pd

from watchscraper.valuation import market_index_from_trends
from watchscraper.web.services import (
    MarketSnapshot,
    _clean_float,
    refs_payload,
    slugify,
)

# Price-range index bands (USD): (slug, label, lo, hi)
PRICE_BANDS = [
    ("under-5k", "Under $5,000", 0, 5_000),
    ("5k-10k", "$5,000–$10,000", 5_000, 10_000),
    ("10k-25k", "$10,000–$25,000", 10_000, 25_000),
    ("25k-plus", "$25,000+", 25_000, float("inf")),
]

# Style groups for group indexes
STYLE_GROUPS = {
    "sports": ("Sports", {"Dive", "Racing", "Pilot", "Field"}),
    "dress": ("Dress", {"Dress"}),
}


def _family_meta(snapshot: MarketSnapshot) -> pd.DataFrame:
    """Per-family brand, style, and value level — the index constituent table."""
    refs = refs_payload(snapshot)
    if not refs:
        return pd.DataFrame()
    df = pd.DataFrame(refs)
    agg = (
        df.groupby("family")
        .agg(
            brand=("brand", "first"),
            style=("style", "first"),
            median_value=("median_usd", "median"),
            n_refs=("ref", "nunique"),
            total_sales=("n_sold", "sum"),
        )
        .reset_index()
    )
    return agg


def _index_stats(series: pd.Series) -> dict:
    if series.empty or len(series) < 2:
        return {"level": None, "chg_1y_pct": None, "points": []}
    return {
        "level": _clean_float(series.iloc[-1]),
        "chg_1y_pct": _clean_float((series.iloc[-1] / series.iloc[0] - 1) * 100),
        "points": [
            {"date": d.strftime("%Y-%m-%d"), "value": _clean_float(v)}
            for d, v in series.items()
        ],
    }


def indexes_payload(snapshot: MarketSnapshot) -> dict:
    """P6: overall + brand + group + price-range indexes."""
    model = snapshot.valuation
    meta = _family_meta(snapshot)
    if meta.empty:
        return {"overall": None, "brands": [], "groups": [], "price_ranges": []}

    overall = _index_stats(market_index_from_trends(model))
    overall.update({"slug": "overall", "name": "Overall Market",
                    "kind": "overall", "n_constituents": int(meta["n_refs"].sum())})

    brands = []
    for brand, grp in meta.groupby("brand"):
        fams = set(grp["family"])
        s = market_index_from_trends(model, families=fams, min_obs=20)
        stats = _index_stats(s)
        if stats["level"] is not None:
            stats.update({"slug": slugify(brand), "name": f"{brand} Market",
                          "kind": "brand", "n_constituents": int(grp["n_refs"].sum())})
            brands.append(stats)
    brands.sort(key=lambda x: -(x["chg_1y_pct"] or -999))

    groups = []
    for slug, (label, styles) in STYLE_GROUPS.items():
        fams = set(meta[meta["style"].isin(styles)]["family"])
        s = market_index_from_trends(model, families=fams, min_obs=20)
        stats = _index_stats(s)
        if stats["level"] is not None:
            stats.update({"slug": slug, "name": f"{label} Watches",
                          "kind": "group", "n_constituents": len(fams)})
            groups.append(stats)

    price_ranges = []
    for slug, label, lo, hi in PRICE_BANDS:
        fams = set(meta[(meta["median_value"] >= lo) & (meta["median_value"] < hi)]["family"])
        s = market_index_from_trends(model, families=fams, min_obs=20)
        stats = _index_stats(s)
        if stats["level"] is not None:
            stats.update({"slug": slug, "name": label, "kind": "price_range",
                          "n_constituents": len(fams)})
            price_ranges.append(stats)

    return {"overall": overall, "brands": brands, "groups": groups,
            "price_ranges": price_ranges}


def index_detail(snapshot: MarketSnapshot, slug: str) -> dict | None:
    """One index's full series + its constituents."""
    payload = indexes_payload(snapshot)
    allix = [payload["overall"]] + payload["brands"] + payload["groups"] + payload["price_ranges"]
    ix = next((i for i in allix if i and i["slug"] == slug), None)
    if ix is None:
        return None
    return ix


def top_performers(
    snapshot: MarketSnapshot,
    brand: str | None = None,
    min_price: float = 0,
    min_trend: float | None = None,
    sort: str = "trend_desc",
    limit: int = 100,
) -> list[dict]:
    """P7: screener over priced references by market metrics."""
    rows = refs_payload(snapshot)
    out = []
    for r in rows:
        if r["median_usd"] is None or r["median_usd"] < min_price:
            continue
        if brand and r["brand"] != brand:
            continue
        # 1m trend proxy; families carry the smoothed change
        trend = r.get("chg_1m_pct")
        if min_trend is not None and (trend is None or trend < min_trend):
            continue
        out.append(r)
    key = {
        "trend_desc": lambda x: -(x.get("chg_1m_pct") or -1e9),
        "trend_asc": lambda x: (x.get("chg_1m_pct") or 1e9),
        "price_desc": lambda x: -(x["median_usd"] or 0),
        "price_asc": lambda x: (x["median_usd"] or 0),
    }.get(sort, lambda x: -(x.get("chg_1m_pct") or -1e9))
    out.sort(key=key)
    return out[:limit]


def value_retention_leaderboard(snapshot: MarketSnapshot) -> list[dict]:
    """P8: per-brand median retention across in-production references."""
    rows = refs_payload(snapshot)
    df = pd.DataFrame(rows)
    if df.empty:
        return []
    inprod = df[df["current"] & df["premium_pct"].notna()]
    board = []
    for brand, grp in inprod.groupby("brand"):
        board.append({
            "brand": brand,
            "slug": slugify(brand),
            "retention_pct": _clean_float(grp["premium_pct"].median()),
            "n_watches": int(len(grp)),
            "best": [
                {"ref": r["ref"], "slug": r["slug"], "display_ref": r["display_ref"],
                 "premium_pct": _clean_float(r["premium_pct"]),
                 "median_usd": _clean_float(r["median_usd"]),
                 "retail_usd": _clean_float(r["retail_usd"])}
                for _, r in grp.nlargest(5, "premium_pct").iterrows()
            ],
            "worst": [
                {"ref": r["ref"], "slug": r["slug"], "display_ref": r["display_ref"],
                 "premium_pct": _clean_float(r["premium_pct"]),
                 "median_usd": _clean_float(r["median_usd"]),
                 "retail_usd": _clean_float(r["retail_usd"])}
                for _, r in grp.nsmallest(5, "premium_pct").iterrows()
            ],
        })
    board.sort(key=lambda x: -(x["retention_pct"] or -999))
    return board


def forecast_leaderboard(snapshot: MarketSnapshot, gated: bool = True) -> list[dict]:
    """P9: per-reference 1-year reasonable forecast + past-year volume.

    Forecast is the family's damped-trend reasonable scenario (families carry
    the trend; a reference inherits it). Gated: the numeric forecast is masked
    unless the caller is entitled."""
    from watchscraper.metrics import compute_metrics

    rows = refs_payload(snapshot)
    out = []
    for r in rows:
        fam_model = snapshot.valuation.families.get(r["family"])
        if fam_model is None:
            continue
        node = snapshot.valuation.node_row(r["brand"], r["ref"], r["dial_variant"], r["family"])
        if node is None:
            continue
        wm = compute_metrics(node, fam_model, retail_usd=r["retail_usd"], sold_dates=None)
        reasonable = wm.forecast_1y.get("reasonable") if wm.forecast_1y else None
        out.append({
            "ref": r["ref"], "slug": r["slug"], "display_ref": r["display_ref"],
            "brand": r["brand"], "family": r["family"], "current": r["current"],
            "median_usd": _clean_float(r["median_usd"]),
            "sales_1y": int(r["n_sold"]),
            "forecast_pct": None if gated else _clean_float(reasonable),
            "forecast_masked": gated,
        })
    out.sort(key=lambda x: -x["sales_1y"])
    return out


def collecting_lists() -> list[dict]:
    """The list catalog (P10). Rules are executed in `collecting_list`."""
    return [
        {"slug": "above-retail", "title": "Trading Above Retail",
         "blurb": "Current-production watches that sell above their retail price on the secondary market.",
         "rule": "in production and market value above retail"},
        {"slug": "steady-gainers", "title": "Steady Gainers",
         "blurb": "References whose smoothed value has risen over the tracked window.",
         "rule": "positive smoothed price trend"},
        {"slug": "comebacks", "title": "Comeback Watches",
         "blurb": "References down over the longer run but turning back up recently.",
         "rule": "negative 3-month, positive 1-month smoothed trend"},
        {"slug": "resilient-sports", "title": "Resilient Sports Watches",
         "blurb": "Dive, racing, and pilot watches holding value better than the market.",
         "rule": "sports style and trend above the overall index"},
    ]


def collecting_list(snapshot: MarketSnapshot, slug: str) -> dict | None:
    lists = {l["slug"]: l for l in collecting_lists()}
    meta = lists.get(slug)
    if meta is None:
        return None
    rows = refs_payload(snapshot)

    overall = market_index_from_trends(snapshot.valuation)
    overall_1m = None
    if not overall.empty and len(overall) > 4:
        overall_1m = (overall.iloc[-1] / overall.iloc[-5] - 1) * 100

    def keep(r) -> bool:
        chg1 = r.get("chg_1m_pct")
        chg3 = None
        node = snapshot.valuation.node_row(r["brand"], r["ref"], r["dial_variant"], r["family"])
        if node is not None:
            chg3 = _clean_float(node.get("chg_3m_pct"))
        if slug == "above-retail":
            return bool(r["current"] and (r["premium_pct"] or 0) > 0)
        if slug == "steady-gainers":
            return bool(chg1 is not None and chg1 > 0.5)
        if slug == "comebacks":
            return bool(chg3 is not None and chg3 < 0 and chg1 is not None and chg1 > 0)
        if slug == "resilient-sports":
            return bool(r.get("style") in ("Dive", "Racing", "Pilot")
                        and chg1 is not None and overall_1m is not None
                        and chg1 > overall_1m)
        return False

    results = [r for r in rows if keep(r)]
    results.sort(key=lambda x: -(x.get("chg_1m_pct") or -1e9))
    return {**meta, "results": results[:60], "n": len(results)}


def search(snapshot: MarketSnapshot, q: str, limit: int = 12) -> dict:
    """Global autocomplete (S0-3): watches, families, brands matching q."""
    q = (q or "").strip().lower()
    if len(q) < 2:
        return {"watches": [], "families": [], "brands": []}
    rows = refs_payload(snapshot)
    watches = []
    for r in rows:
        hay = " ".join(str(x).lower() for x in [
            r["ref"], r["brand"], r["family"], r["display_ref"],
            *(r.get("nicknames") or []),
        ])
        if q in hay:
            watches.append({
                "slug": r["slug"], "display_ref": r["display_ref"],
                "brand": r["brand"], "family": r["family"],
                "median_usd": _clean_float(r["median_usd"]), "image": r["image"],
                "nicknames": r.get("nicknames") or [],
            })
    watches.sort(key=lambda x: (0 if x["display_ref"].lower().startswith(q) else 1,
                                -(x["median_usd"] or 0)))
    families = sorted({r["family"] for r in rows
                       if r["family"] and q in r["family"].lower()})
    brands = sorted({r["brand"] for r in rows if q in r["brand"].lower()})
    return {
        "watches": watches[:limit],
        "families": [{"name": f, "slug": slugify(f)} for f in families[:6]],
        "brands": [{"name": b, "slug": slugify(b)} for b in brands[:6]],
    }
