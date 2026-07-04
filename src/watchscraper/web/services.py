"""Market data services for the web app.

The clean dataset takes seconds to build, so it is computed once and cached
with a TTL. Everything the pages need derives from this one snapshot, so all
views agree with each other.
"""

import math
import re
import threading
import time
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from sqlalchemy import text as sa_text

from watchscraper.analysis import (
    build_clean_dataset,
    cleaning_report,
    dominant_material,
    dominant_weekly,
    material_breakdown,
    reference_values,
    weekly_medians,
)
from watchscraper.database import engine
from watchscraper.quant import (
    build_market_index,
    family_signals,
    forecast_families,
    forecast_series,
)
from watchscraper.valuation import (
    ValuationModel,
    build_valuation,
    market_index_from_trends,
)

CACHE_TTL_SECONDS = 900

_STATIC_DIR = None


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _static_dir():
    global _STATIC_DIR
    if _STATIC_DIR is None:
        from pathlib import Path

        _STATIC_DIR = Path(__file__).resolve().parent / "static"
    return _STATIC_DIR


def family_image(slug: str) -> str | None:
    """URL of the family's image if we have one on disk."""
    if (_static_dir() / "img" / "families" / f"{slug}.jpg").exists():
        return f"/static/img/families/{slug}.jpg"
    return None


def ref_image(
    slug: str, family_slug: str | None = None, parent_slug: str | None = None
) -> str | None:
    """The watch's own image, falling back variant → reference → family."""
    if (_static_dir() / "img" / "refs" / f"{slug}.jpg").exists():
        return f"/static/img/refs/{slug}.jpg"
    if parent_slug and (_static_dir() / "img" / "refs" / f"{parent_slug}.jpg").exists():
        return f"/static/img/refs/{parent_slug}.jpg"
    return family_image(family_slug) if family_slug else None


@dataclass
class MarketSnapshot:
    df: pd.DataFrame
    weekly: pd.DataFrame  # material-stratified
    dom_weekly: pd.DataFrame  # each family's dominant material stratum only
    signals: pd.DataFrame
    index: pd.Series
    index_forecast: pd.DataFrame | None
    forecasts: dict[str, pd.DataFrame]
    report: dict
    dominant: dict[str, str] = field(default_factory=dict)
    breakdown: pd.DataFrame = field(default_factory=pd.DataFrame)
    dom_by_family: dict[str, float] = field(default_factory=dict)
    active_by_family: dict[str, int] = field(default_factory=dict)
    valuation: ValuationModel = field(default_factory=ValuationModel)
    ref_values: pd.DataFrame = field(default_factory=pd.DataFrame)
    nicknames_by_ref: dict[tuple[str, str], list[str]] = field(default_factory=dict)
    catalog_watches: pd.DataFrame = field(default_factory=pd.DataFrame)
    computed_at: float = field(default_factory=time.time)

    def family_row(self, slug: str) -> pd.Series | None:
        for _, row in self.signals.iterrows():
            if slugify(row["family"]) == slug:
                return row
        return None

    def ref_row(self, slug: str) -> pd.Series | None:
        """Find a priced watch by its slug (brand + ref + dial variant)."""
        for _, row in self.ref_values.iterrows():
            if ref_slug(row["brand"], row["ref"], row.get("dial_variant")) == slug:
                return row
        return None


def days_on_market_by_family_cached() -> dict[str, float]:
    from watchscraper.database import get_session
    from watchscraper.listings import days_on_market_by_family

    s = get_session()
    try:
        return days_on_market_by_family(s)
    finally:
        s.close()


def active_counts_by_family_cached() -> dict[str, int]:
    from watchscraper.database import get_session
    from watchscraper.listings import active_counts_by_family

    s = get_session()
    try:
        return active_counts_by_family(s)
    finally:
        s.close()


def ref_slug(brand: str, ref: str, dial_variant: str | None = None) -> str:
    if dial_variant and pd.notna(dial_variant):
        return slugify(f"{brand} {ref} {dial_variant}")
    return slugify(f"{brand} {ref}")


_lock = threading.Lock()
_snapshot: MarketSnapshot | None = None


def get_market(refresh: bool = False) -> MarketSnapshot:
    global _snapshot
    with _lock:
        if (
            _snapshot is None
            or refresh
            or time.time() - _snapshot.computed_at > CACHE_TTL_SECONDS
        ):
            df = build_clean_dataset(engine)
            weekly = weekly_medians(df)
            dominant = dominant_material(df)
            dom_weekly = dominant_weekly(weekly, dominant)
            signals = family_signals(df, dom_weekly, dominant)
            valuation = build_valuation(
                df[df["clean"] & (df["price_type"] == "sold")]
            )
            index = market_index_from_trends(valuation)
            if index.empty:
                index = build_market_index(weekly)
            index_fc = forecast_series(index) if not index.empty else None
            forecasts = forecast_families(dom_weekly)
            catalog_watches = pd.read_sql(
                sa_text("""
                    SELECT b.name AS brand, w.reference_number AS ref,
                           w.dial_variant, w.family, w.case_material,
                           w.production_start_year AS start_year,
                           w.production_end_year AS end_year,
                           w.retail_price_usd / 100.0 AS retail_usd,
                           w.case_size_mm, w.dial_color, w.bezel, w.bracelet,
                           w.movement, w.style, w.complications, w.features,
                           w.movement_type, w.frequency_bph, w.jewels,
                           w.power_reserve_hours, w.crystal, w.dial_numerals,
                           w.lug_width_mm, w.water_resistance_m, w.case_thickness_mm
                    FROM watches w JOIN brands b ON b.id = w.brand_id
                """),
                engine,
            )
            from watchscraper.listings import (
                active_counts_by_family,
                days_on_market_by_family,
            )

            dom_by_family = days_on_market_by_family_cached()
            active_by_family = active_counts_by_family_cached()
            nick_rows = pd.read_sql(
                sa_text("""
                    SELECT w.reference_number AS ref,
                           COALESCE(w.dial_variant, '') AS dial,
                           n.nickname
                    FROM watch_nicknames n JOIN watches w ON w.id = n.watch_id
                """),
                engine,
            )
            nicknames_by_ref: dict[tuple[str, str], list[str]] = {}
            for _, r in nick_rows.iterrows():
                nicknames_by_ref.setdefault((r["ref"], r["dial"]), []).append(
                    r["nickname"]
                )
            _snapshot = MarketSnapshot(
                df=df,
                weekly=weekly,
                dom_weekly=dom_weekly,
                signals=signals,
                index=index,
                index_forecast=index_fc,
                forecasts=forecasts,
                report=cleaning_report(df),
                dominant=dominant,
                breakdown=material_breakdown(df),
                dom_by_family=dom_by_family,
                active_by_family=active_by_family,
                valuation=valuation,
                ref_values=reference_values(df),
                nicknames_by_ref=nicknames_by_ref,
                catalog_watches=catalog_watches,
            )
    return _snapshot


def _clean_float(v) -> float | None:
    """JSON-safe float: NaN/inf become None."""
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if (math.isnan(f) or math.isinf(f)) else f


def series_points(s: pd.Series) -> list[dict]:
    return [
        {"date": idx.strftime("%Y-%m-%d"), "value": _clean_float(val)}
        for idx, val in s.items()
        if _clean_float(val) is not None
    ]


def family_weekly_series(
    snapshot: MarketSnapshot, family: str, price_type: str = "sold"
) -> pd.DataFrame:
    """The family's composition-stable series: its dominant material stratum."""
    grp = snapshot.dom_weekly[
        (snapshot.dom_weekly["family"] == family)
        & (snapshot.dom_weekly["price_type"] == price_type)
    ]
    return grp.sort_values("week")


def signals_payload(snapshot: MarketSnapshot) -> list[dict]:
    """Signal table + sparkline series for the explorer grid."""
    rows = []
    for _, r in snapshot.signals.iterrows():
        weekly = family_weekly_series(snapshot, r["family"])
        spark = [_clean_float(v) for v in weekly["median"]]
        rows.append(
            {
                "brand": r["brand"],
                "family": r["family"],
                "slug": slugify(r["family"]),
                "image": family_image(slugify(r["family"])),
                "tier": r["tier"],
                "n_sold": int(r["n_sold"]),
                "median_usd": _clean_float(r["median_usd"]),
                "median_ci_lo": _clean_float(r["median_ci_lo"]),
                "median_ci_hi": _clean_float(r["median_ci_hi"]),
                "trend_pct_mo": _clean_float(r["trend_pct_mo"]),
                "mk_pvalue": _clean_float(r["mk_pvalue"]),
                "vol_ann_pct": _clean_float(r["vol_ann_pct"]),
                "momentum_pct": _clean_float(r["momentum_pct"]),
                "ask_sold_spread_pct": _clean_float(r["ask_sold_spread_pct"]),
                "premium_to_retail_pct": _clean_float(r["premium_to_retail_pct"]),
                "n_weeks": int(r["n_weeks"]),
                "sparkline": [v for v in spark if v is not None],
            }
        )
    return rows


def forecast_payload(fc: pd.DataFrame | None) -> list[dict]:
    if fc is None:
        return []
    return [
        {
            "date": r["week"].strftime("%Y-%m-%d"),
            "forecast": _clean_float(r["forecast"]),
            "p05": _clean_float(r["p05"]),
            "p25": _clean_float(r["p25"]),
            "p75": _clean_float(r["p75"]),
            "p95": _clean_float(r["p95"]),
        }
        for _, r in fc.iterrows()
    ]


def family_detail_payload(snapshot: MarketSnapshot, slug: str) -> dict | None:
    row = snapshot.family_row(slug)
    if row is None:
        return None
    family = row["family"]

    # Smooth family value line from the valuation model (standard config,
    # composition-adjusted) — weekly medians of whoever-sold-that-week are
    # composition noise and are no longer plotted as a line
    history = []
    fam_model = snapshot.valuation.families.get(family)
    if fam_model is not None:
        import numpy as _np

        se = _np.sqrt(fam_model.trend_se**2)
        values = _np.exp(fam_model.base + fam_model.trend)
        los = _np.exp(fam_model.base + fam_model.trend - 1.96 * se)
        his = _np.exp(fam_model.base + fam_model.trend + 1.96 * se)
        history = [
            {
                "date": d.strftime("%Y-%m-%d"),
                "median": _clean_float(v),
                "p25": _clean_float(lo),
                "p75": _clean_float(hi),
            }
            for d, v, lo, hi in zip(fam_model.grid, values, los, his)
        ]

    weekly_ask = family_weekly_series(snapshot, family, "asking")
    asking_history = [
        {
            "date": r["week"].strftime("%Y-%m-%d"),
            "median": _clean_float(r["median"]),
            "n": int(r["n"]),
        }
        for _, r in weekly_ask.iterrows()
    ]

    clean = snapshot.df[snapshot.df["clean"]]
    fam_records = clean[clean["family"] == family]
    sold = fam_records[fam_records["price_type"] == "sold"].sort_values(
        "event_date", ascending=False
    )
    recent_sales = [
        {
            "date": r["event_date"].strftime("%Y-%m-%d"),
            "title": (r["title"] or "")[:110],
            "price": _clean_float(r["price"]),
            "condition": r["condition"],
            "source": r["source"],
        }
        for _, r in sold.head(30).iterrows()
    ]

    # References in this family: each reference is a watch with its own
    # value derived from confidence-filtered sold prices of the variant
    refs = []
    if not snapshot.ref_values.empty:
        fam_refs = snapshot.ref_values[
            snapshot.ref_values["family"] == family
        ].sort_values("n_sold", ascending=False)
        for _, r in fam_refs.head(15).iterrows():
            row_payload = _ref_value_row(snapshot, r)
            refs.append(
                {
                    "ref": row_payload["display_ref"],
                    "slug": row_payload["slug"],
                    "image": row_payload["image"],
                    "model": r["model"],
                    "years": row_payload["years"],
                    "nicknames": row_payload["nicknames"],
                    "n": int(r["n_sold"]),
                    "median": _clean_float(r["median_usd"]),
                    "p25": _clean_float(r["p25_usd"]),
                    "p75": _clean_float(r["p75_usd"]),
                    "retail": _clean_float(r["retail_usd"]),
                    "premium_pct": _clean_float(r["premium_to_retail_pct"]),
                }
            )

    materials = []
    if not snapshot.breakdown.empty:
        fam_break = snapshot.breakdown[
            snapshot.breakdown["family"] == family
        ].sort_values("n", ascending=False)
        materials = [
            {
                "material": r["material"],
                "n": int(r["n"]),
                "median": _clean_float(r["median"]),
                "dominant": snapshot.dominant.get(family) == r["material"],
            }
            for _, r in fam_break.iterrows()
        ]

    # Forecast from the smoothed trend, damped
    forecast_points = []
    fc = snapshot.valuation.forecast_trend(family)
    if fc is not None and fam_model is not None:
        import numpy as _np

        for _, r in fc.iterrows():
            forecast_points.append(
                {
                    "date": r["week"].strftime("%Y-%m-%d"),
                    "forecast": _clean_float(float(_np.exp(fam_model.base + r["trend"]))),
                    "p05": _clean_float(float(_np.exp(fam_model.base + r["p05"]))),
                    "p95": _clean_float(float(_np.exp(fam_model.base + r["p95"]))),
                }
            )

    chg_1m = chg_3m = None
    if fam_model is not None and len(fam_model.trend) > 4:
        chg_1m = _clean_float(
            float((np.exp(fam_model.trend[-1] - fam_model.trend[-5]) - 1) * 100)
        )
        if len(fam_model.trend) > 12:
            chg_3m = _clean_float(
                float((np.exp(fam_model.trend[-1] - fam_model.trend[-13]) - 1) * 100)
            )

    return {
        "brand": row["brand"],
        "family": family,
        "slug": slug,
        "image": family_image(slug),
        "materials": materials,
        "dominant_material": snapshot.dominant.get(family),
        "chg_1m_pct": chg_1m,
        "chg_3m_pct": chg_3m,
        "tier": row["tier"],
        "signals": signals_payload_row(row),
        "history": history,
        "asking_history": asking_history,
        "forecast": forecast_points,
        "recent_sales": recent_sales,
        "references": refs,
    }


def signals_payload_row(r: pd.Series) -> dict:
    return {
        "n_sold": int(r["n_sold"]),
        "median_usd": _clean_float(r["median_usd"]),
        "median_ci_lo": _clean_float(r["median_ci_lo"]),
        "median_ci_hi": _clean_float(r["median_ci_hi"]),
        "trend_pct_mo": _clean_float(r["trend_pct_mo"]),
        "mk_pvalue": _clean_float(r["mk_pvalue"]),
        "vol_ann_pct": _clean_float(r["vol_ann_pct"]),
        "momentum_pct": _clean_float(r["momentum_pct"]),
        "ask_sold_spread_pct": _clean_float(r["ask_sold_spread_pct"]),
        "premium_to_retail_pct": _clean_float(r["premium_to_retail_pct"]),
        "n_weeks": int(r["n_weeks"]),
    }


def _years_label(start, end) -> str | None:
    if pd.isna(start) or start is None:
        return None
    return f"{int(start)}–{int(end) if pd.notna(end) and end is not None else 'now'}"


def _ref_value_row(snapshot: MarketSnapshot, r: pd.Series) -> dict:
    fam_slug = slugify(r["family"]) if r["family"] else None
    dial = r.get("dial_variant")
    dial = dial if (dial and pd.notna(dial)) else None
    slug = ref_slug(r["brand"], r["ref"], dial)
    parent_slug = ref_slug(r["brand"], r["ref"]) if dial else None

    # Headline value comes from the hierarchical valuation model (smooth,
    # configuration-standardized); the comps median stays as evidence
    value = _clean_float(r["median_usd"])
    ci_lo = _clean_float(r["p25_usd"])
    ci_hi = _clean_float(r["p75_usd"])
    chg_1m = None
    node = snapshot.valuation.node_row(r["brand"], r["ref"], dial, r["family"])
    if node is not None and node["node_type"] in ("variant", "ref"):
        value = _clean_float(node["value"])
        ci_lo = _clean_float(node["ci_lo"])
        ci_hi = _clean_float(node["ci_hi"])
        chg_1m = _clean_float(node["chg_1m_pct"])

    retail = _clean_float(r["retail_usd"])
    return {
        "comps_median_usd": _clean_float(r["median_usd"]),
        "chg_1m_pct": chg_1m,
        "brand": r["brand"],
        "ref": r["ref"],
        "dial_variant": dial,
        "display_ref": f"{r['ref']} · {dial} dial" if dial else r["ref"],
        "slug": slug,
        "model": r["model"],
        "family": r["family"],
        "family_slug": fam_slug,
        "years": _years_label(r["start_year"], r["end_year"]),
        "current": pd.isna(r["end_year"]) and pd.notna(r["start_year"]),
        "nicknames": snapshot.nicknames_by_ref.get((r["ref"], dial or ""), []),
        "image": ref_image(slug, fam_slug, parent_slug),
        "n_sold": int(r["n_sold"]),
        "median_usd": value,
        "p25_usd": ci_lo,
        "p75_usd": ci_hi,
        "retail_usd": retail,
        "premium_pct": _clean_float(
            (value / retail - 1) * 100 if (retail and value) else None
        ),
    }


def refs_payload(snapshot: MarketSnapshot) -> list[dict]:
    """Every priced reference — the first-class browse unit, with spec facets."""
    if snapshot.ref_values.empty:
        return []
    # Index specs by (brand, ref) for filter facets on the cards
    spec_index: dict[tuple, dict] = {}
    if not snapshot.catalog_watches.empty:
        for _, w in snapshot.catalog_watches.iterrows():
            spec_index.setdefault((w["brand"], w["ref"]), w)

    rows = []
    for _, r in snapshot.ref_values.iterrows():
        row = _ref_value_row(snapshot, r)
        w = spec_index.get((r["brand"], r["ref"]))
        if w is not None:
            row["style"] = w["style"] if pd.notna(w["style"]) else None
            row["case_material"] = w["case_material"] if pd.notna(w["case_material"]) else None
            row["movement_type"] = w["movement_type"] if pd.notna(w["movement_type"]) else None
            row["case_size_mm"] = _clean_float(w["case_size_mm"])
        rows.append(row)
    return rows


def ref_detail_payload(snapshot: MarketSnapshot, slug: str) -> dict | None:
    row = snapshot.ref_row(slug)
    if row is None:
        return None
    payload = _ref_value_row(snapshot, row)
    brand, ref, family = row["brand"], row["ref"], row["family"]
    dial = payload["dial_variant"]

    from watchscraper.analysis import REF_VALUE_MIN_CONFIDENCE
    from watchscraper.quant import bootstrap_median_ci

    clean = snapshot.df[snapshot.df["clean"]]
    ref_sold = clean[
        (clean["linked_ref"] == ref)
        & (clean["linked_brand"] == brand)
        & (
            clean["linked_dial"] == dial
            if dial
            else clean["linked_dial"].isna()
        )
        & (clean["price_type"] == "sold")
        & (clean["match_confidence"].fillna(0) >= REF_VALUE_MIN_CONFIDENCE)
    ].sort_values("event_date")

    ci_lo, ci_hi = bootstrap_median_ci(ref_sold["price"].values)
    payload["median_ci_lo"] = _clean_float(ci_lo)
    payload["median_ci_hi"] = _clean_float(ci_hi)

    # Valuation: smooth market value from the hierarchical model — the
    # line the persona reads; individual sales are plotted as evidence
    node = snapshot.valuation.node_row(brand, ref, dial, family)
    payload["valuation"] = None
    if node is not None:
        series = snapshot.valuation.value_series(node)
        lo, hi = snapshot.valuation.value_band(node)
        fc = snapshot.valuation.forecast_trend(family)
        fam_model = snapshot.valuation.families.get(family)
        forecast_points = []
        if fc is not None and fam_model is not None:
            base_off = fam_model.base + node["offset"]
            for _, r in fc.iterrows():
                forecast_points.append(
                    {
                        "date": r["week"].strftime("%Y-%m-%d"),
                        "value": _clean_float(float(np.exp(base_off + r["trend"]))),
                        "p05": _clean_float(float(np.exp(base_off + r["p05"]))),
                        "p95": _clean_float(float(np.exp(base_off + r["p95"]))),
                    }
                )
        payload["valuation"] = {
            "value": _clean_float(node["value"]),
            "ci_lo": _clean_float(node["ci_lo"]),
            "ci_hi": _clean_float(node["ci_hi"]),
            "chg_1m_pct": _clean_float(node["chg_1m_pct"]),
            "chg_3m_pct": _clean_float(node["chg_3m_pct"]),
            "node_type": node["node_type"],
            "series": [
                {
                    "date": d.strftime("%Y-%m-%d"),
                    "value": _clean_float(v),
                    "lo": _clean_float(lo.get(d)),
                    "hi": _clean_float(hi.get(d)),
                }
                for d, v in series.items()
            ],
            "forecast": forecast_points,
            "full_set_premium_pct": _clean_float(
                (np.exp(snapshot.valuation.hedonics.get("full_set", 0)) - 1) * 100
                if "full_set" in snapshot.valuation.hedonics
                else None
            ),
        }

    # WatchCharts-style metric suite (value retention, volatility, risk
    # score, sales volume, forecast fan, inception)
    from watchscraper.metrics import compute_metrics

    payload["metrics"] = None
    node2 = snapshot.valuation.node_row(brand, ref, dial, family)
    fam_model2 = snapshot.valuation.families.get(family)
    if node2 is not None and fam_model2 is not None:
        wm = compute_metrics(
            node2, fam_model2,
            retail_usd=payload.get("retail_usd"),
            sold_dates=ref_sold["event_date"] if len(ref_sold) else None,
        )
        payload["metrics"] = {
            "value_retention_pct": wm.value_retention_pct,
            "market_volatility_pct": wm.market_volatility_pct,
            "risk_score": wm.risk_score,
            "risk_band": wm.risk_band,
            "risk_components": wm.risk_components,
            "sales_1y": wm.sales_1y,
            "market_inception": wm.market_inception,
            "forecast_1y": wm.forecast_1y,
            "median_days_on_market": _clean_float(snapshot.dom_by_family.get(family)),
            "active_listings": snapshot.active_by_family.get(family),
        }

    # Full spec sheet (WatchCharts "Model Specifications")
    payload["specs"] = None
    if not snapshot.catalog_watches.empty:
        cw = snapshot.catalog_watches
        hit = cw[
            (cw["brand"] == brand)
            & (cw["ref"] == ref)
            & (cw["dial_variant"].fillna("") == (dial or ""))
        ]
        if hit.empty:  # variant may inherit from the parent row
            hit = cw[(cw["brand"] == brand) & (cw["ref"] == ref)]
        if not hit.empty:
            w = hit.iloc[0]

            def _s(v):
                return None if (v is None or (isinstance(v, float) and pd.isna(v))) else v

            payload["specs"] = {
                "Basic Info": {
                    "Brand": brand,
                    "Collection": family,
                    "Reference": ref,
                    "Style": _s(w["style"]),
                    "Complications": _s(w["complications"]),
                    "Features": _s(w["features"]),
                    "Production": (
                        payload["years"] + (" · in production" if payload["current"] else " · discontinued")
                        if payload["years"] else None
                    ),
                },
                "Case": {
                    "Case Diameter": f"{w['case_size_mm']:.0f}mm" if _s(w["case_size_mm"]) else None,
                    "Case Thickness": f"{w['case_thickness_mm']:.1f}mm" if _s(w["case_thickness_mm"]) else None,
                    "Case Material": _s(w["case_material"]),
                    "Bezel Material": _s(w["bezel"]),
                    "Dial Color": dial or _s(w["dial_color"]),
                    "Dial Numerals": _s(w["dial_numerals"]),
                    "Crystal": _s(w["crystal"]),
                    "Lug Width": f"{w['lug_width_mm']:.0f}mm" if _s(w["lug_width_mm"]) else None,
                    "Water Resistance": f"{int(w['water_resistance_m'])}M" if _s(w["water_resistance_m"]) else None,
                    "Bracelet": _s(w["bracelet"]),
                },
                "Movement": {
                    "Movement Type": _s(w["movement_type"]),
                    "Caliber": _s(w["movement"]),
                    "Frequency": f"{int(w['frequency_bph'])} bph" if _s(w["frequency_bph"]) else None,
                    "Number of Jewels": int(w["jewels"]) if _s(w["jewels"]) else None,
                    "Power Reserve": f"{int(w['power_reserve_hours'])} hours" if _s(w["power_reserve_hours"]) else None,
                },
            }

    # Round-trip cost: buy at dealer ask, sell at market — the immediate
    # loss the persona takes on a flip
    fam_signal = snapshot.signals[snapshot.signals["family"] == family]
    spread = (
        _clean_float(fam_signal["ask_sold_spread_pct"].iloc[0])
        if len(fam_signal)
        else None
    )
    payload["round_trip_pct"] = spread

    # Individual sales as scatter points — honest at reference sample sizes
    payload["sales_points"] = [
        {
            "date": r["event_date"].strftime("%Y-%m-%d"),
            "value": _clean_float(r["price"]),
            "method": r["match_method"],
        }
        for _, r in ref_sold.iterrows()
    ]

    payload["recent_sales"] = [
        {
            "date": r["event_date"].strftime("%Y-%m-%d"),
            "title": (r["title"] or "")[:110],
            "price": _clean_float(r["price"]),
            "method": r["match_method"],
            "confidence": _clean_float(r["match_confidence"]),
        }
        for _, r in ref_sold.sort_values("event_date", ascending=False).head(25).iterrows()
    ]

    # THE VARIANT MATRIX: every cataloged variant of this reference —
    # each dial is its own market with its own value, or an honest
    # "no cleared sales yet". Nothing is averaged across variants.
    variants = []
    if not snapshot.catalog_watches.empty:
        same_ref = snapshot.catalog_watches[
            (snapshot.catalog_watches["brand"] == brand)
            & (snapshot.catalog_watches["ref"] == ref)
            & (snapshot.catalog_watches["dial_variant"].notna())
        ]
        for _, w in same_ref.iterrows():
            w_dial = w["dial_variant"]
            node = None
            if not snapshot.valuation.nodes.empty:
                hits = snapshot.valuation.nodes[
                    (snapshot.valuation.nodes["brand"] == brand)
                    & (snapshot.valuation.nodes["ref"] == ref)
                    & (snapshot.valuation.nodes["dial_variant"] == w_dial)
                ]
                node = hits.iloc[0] if len(hits) else None
            v_slug = ref_slug(brand, ref, w_dial)
            priced = snapshot.ref_row(v_slug) is not None
            variants.append(
                {
                    "dial": w_dial,
                    "material": w["case_material"],
                    "slug": v_slug if priced else None,
                    "current_page": w_dial == dial,
                    "value": _clean_float(node["value"]) if node is not None else None,
                    "ci_lo": _clean_float(node["ci_lo"]) if node is not None else None,
                    "ci_hi": _clean_float(node["ci_hi"]) if node is not None else None,
                    "n": int(node["n"]) if node is not None else 0,
                    "retail": _clean_float(w["retail_usd"]),
                    "nicknames": snapshot.nicknames_by_ref.get((ref, w_dial), []),
                }
            )
        variants.sort(key=lambda x: -(x["value"] or 0))
    payload["variants"] = variants

    # Related references in the family (other refs, best-priced variant each)
    siblings = snapshot.ref_values[
        (snapshot.ref_values["family"] == family)
        & (snapshot.ref_values["ref"] != ref)
    ].sort_values("median_usd", ascending=False)
    payload["siblings"] = [
        _ref_value_row(snapshot, s) for _, s in siblings.head(10).iterrows()
    ]
    return payload


def overview_payload(snapshot: MarketSnapshot) -> dict:
    index_points = series_points(snapshot.index)
    idx_change_pct = None
    if len(snapshot.index) >= 2:
        idx_change_pct = _clean_float(
            (snapshot.index.iloc[-1] / snapshot.index.iloc[0] - 1) * 100
        )

    sig = snapshot.signals
    movers = sig[sig["momentum_pct"].notna()]
    gainers = movers.nlargest(5, "momentum_pct")
    losers = movers.nsmallest(5, "momentum_pct")

    def mover_rows(rows):
        return [
            {
                "family": r["family"],
                "slug": slugify(r["family"]),
                "brand": r["brand"],
                "momentum_pct": _clean_float(r["momentum_pct"]),
                "median_usd": _clean_float(r["median_usd"]),
            }
            for _, r in rows.iterrows()
        ]

    clean = snapshot.df[snapshot.df["clean"]]
    return {
        "kpis": {
            "index_level": _clean_float(
                snapshot.index.iloc[-1] if not snapshot.index.empty else None
            ),
            "index_change_pct": idx_change_pct,
            "n_families": int(sig["family"].nunique()),
            "n_clean_records": int(len(clean)),
            "n_sold": int((clean["price_type"] == "sold").sum()),
            "week_start": (
                snapshot.index.index[0].strftime("%b %d, %Y")
                if not snapshot.index.empty
                else None
            ),
        },
        "index": index_points,
        "index_forecast": forecast_payload(snapshot.index_forecast),
        "gainers": mover_rows(gainers),
        "losers": mover_rows(losers),
        "quality": snapshot.report,
    }


def buying_guide_payload(snapshot: MarketSnapshot) -> list[dict]:
    """Rank families for a buyer who doesn't want to lose money.

    Components, in the order the persona feels them:
      - round-trip cost (ask/sold spread): the loss you take the day you
        buy at dealer ask — the single biggest "losing money" mechanism
      - smoothed 1-month trend from the valuation model: is the market for
        this watch drifting up or bleeding?
      - liquidity: can you actually exit near the marked price?
    It is a screen, not advice.
    """
    rows = []
    for r in signals_payload(snapshot):
        if r["median_usd"] is None or r["n_sold"] < 30:
            continue
        fam_model = snapshot.valuation.families.get(r["family"])
        chg_1m = None
        if fam_model is not None and len(fam_model.trend) > 4:
            chg_1m = float(
                (np.exp(fam_model.trend[-1] - fam_model.trend[-5]) - 1) * 100
            )
        spread = r["ask_sold_spread_pct"]

        score = 0.0
        reasons = []
        if spread is not None:
            if spread <= 15:
                score += 3.0
                reasons.append("low round-trip cost")
            elif spread <= 25:
                score += 1.5
                reasons.append("moderate round-trip cost")
        if chg_1m is not None:
            if chg_1m >= 1.0:
                score += 2.0
                reasons.append("value drifting up")
            elif chg_1m >= -1.0:
                score += 1.0
                reasons.append("value holding steady")
        if r["n_sold"] >= 100:
            score += 1.0
            reasons.append("deep market")
        rows.append(
            {**r, "score": round(score, 2), "reasons": reasons,
             "chg_1m_pct": _clean_float(chg_1m), "round_trip_pct": spread}
        )
    rows.sort(key=lambda x: (x["score"], -(x["round_trip_pct"] or 99)), reverse=True)
    return rows


# ── Appraisal (P12) ─────────────────────────────────────────────────────────

# Condition multipliers relative to the "good" reference the model values at.
# Grounded in typical secondary-market spreads; new/unworn matches the ~+4%
# WatchCharts shows.
CONDITION_MULT = {
    "new": 1.04,
    "unworn": 1.04,
    "excellent": 1.015,
    "good": 1.0,
    "fair": 0.92,
}


def _contents_mults(snapshot: MarketSnapshot) -> dict[str, float]:
    """Completeness multipliers. The model values at 'full set'; a naked head
    is discounted by the full-set hedonic, box/papers-partial interpolated."""
    fs = snapshot.valuation.hedonics.get("full_set", 0.10)  # log premium
    watch_only = 1.0 / np.exp(fs)  # remove the full-set premium
    return {
        "full_set": 1.0,
        "with_papers": 1.0 - (1.0 - watch_only) * 0.4,
        "with_box": 1.0 - (1.0 - watch_only) * 0.6,
        "watch_only": watch_only,
    }


def appraise(
    snapshot: MarketSnapshot, slug: str, condition: str, contents: str
) -> dict | None:
    """Estimate a specific example's value: base × condition × completeness."""
    row = snapshot.ref_row(slug)
    if row is None:
        return None
    base = _ref_value_row(snapshot, row)
    value = base["median_usd"]
    if value is None:
        return None
    cond_m = CONDITION_MULT.get(condition, 1.0)
    cont_m = _contents_mults(snapshot).get(contents, 1.0)
    est = value * cond_m * cont_m
    return {
        "slug": slug,
        "display_ref": base["display_ref"],
        "brand": base["brand"],
        "family": base["family"],
        "base_value": value,
        "condition": condition,
        "contents": contents,
        "condition_mult": round(cond_m, 4),
        "contents_mult": round(cont_m, 4),
        "estimate": round(est, 0),
        "estimate_lo": round(est * 0.94, 0),
        "estimate_hi": round(est * 1.06, 0),
        "image": base["image"],
    }


# ── Brand pages (P5b) ───────────────────────────────────────────────────────


def brands_payload(snapshot: MarketSnapshot) -> list[dict]:
    """All brands with aggregate stats, for the brands index (P5a)."""
    rows = refs_payload(snapshot)
    df = pd.DataFrame(rows)
    if df.empty:
        return []
    out = []
    for brand, grp in df.groupby("brand"):
        out.append({
            "brand": brand,
            "slug": slugify(brand),
            "n_refs": int(grp["ref"].nunique()),
            "median_value": _clean_float(grp["median_usd"].median()),
            "total_sales": int(grp["n_sold"].sum()),
        })
    out.sort(key=lambda x: -x["total_sales"])
    return out


def brand_detail_payload(snapshot: MarketSnapshot, slug: str) -> dict | None:
    """One brand: index series, collections, top references (P5b)."""
    from watchscraper.web import research

    rows = refs_payload(snapshot)
    brand_refs = [r for r in rows if slugify(r["brand"]) == slug]
    if not brand_refs:
        return None
    brand = brand_refs[0]["brand"]

    idx = research.index_detail(snapshot, slug)
    fams = {}
    for r in brand_refs:
        fam = r["family"]
        if fam is None:
            continue
        fams.setdefault(fam, {"family": fam, "family_slug": r["family_slug"],
                              "n_refs": 0, "values": [], "image": r["image"]})
        fams[fam]["n_refs"] += 1
        if r["median_usd"]:
            fams[fam]["values"].append(r["median_usd"])
    collections = [
        {"family": f["family"], "family_slug": f["family_slug"], "n_refs": f["n_refs"],
         "median_value": _clean_float(float(np.median(f["values"])) if f["values"] else None),
         "image": f["image"]}
        for f in fams.values()
    ]
    collections.sort(key=lambda x: -(x["median_value"] or 0))

    top = sorted(brand_refs, key=lambda x: -x["n_sold"])[:12]
    return {
        "brand": brand,
        "slug": slug,
        "index": idx,
        "n_refs": len(brand_refs),
        "median_value": _clean_float(float(np.median([r["median_usd"] for r in brand_refs if r["median_usd"]]))),
        "collections": collections,
        "top_refs": top,
    }
