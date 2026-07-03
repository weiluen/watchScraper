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


def ref_image(slug: str, family_slug: str | None = None) -> str | None:
    """The reference's own image, falling back to its family's."""
    if (_static_dir() / "img" / "refs" / f"{slug}.jpg").exists():
        return f"/static/img/refs/{slug}.jpg"
    return family_image(family_slug) if family_slug else None


@dataclass
class MarketSnapshot:
    df: pd.DataFrame
    weekly: pd.DataFrame
    signals: pd.DataFrame
    index: pd.Series
    index_forecast: pd.DataFrame | None
    forecasts: dict[str, pd.DataFrame]
    report: dict
    ref_values: pd.DataFrame = field(default_factory=pd.DataFrame)
    nicknames_by_ref: dict[str, list[str]] = field(default_factory=dict)
    computed_at: float = field(default_factory=time.time)

    def family_row(self, slug: str) -> pd.Series | None:
        for _, row in self.signals.iterrows():
            if slugify(row["family"]) == slug:
                return row
        return None

    def ref_row(self, slug: str) -> pd.Series | None:
        """Find a priced reference by its slug (brand + ref, slugified)."""
        for _, row in self.ref_values.iterrows():
            if ref_slug(row["brand"], row["ref"]) == slug:
                return row
        return None


def ref_slug(brand: str, ref: str) -> str:
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
            signals = family_signals(df, weekly)
            index = build_market_index(weekly)
            index_fc = forecast_series(index) if not index.empty else None
            forecasts = forecast_families(weekly)
            nick_rows = pd.read_sql(
                sa_text("""
                    SELECT w.reference_number AS ref, n.nickname
                    FROM watch_nicknames n JOIN watches w ON w.id = n.watch_id
                """),
                engine,
            )
            nicknames_by_ref: dict[str, list[str]] = {}
            for _, r in nick_rows.iterrows():
                nicknames_by_ref.setdefault(r["ref"], []).append(r["nickname"])
            _snapshot = MarketSnapshot(
                df=df,
                weekly=weekly,
                signals=signals,
                index=index,
                index_forecast=index_fc,
                forecasts=forecasts,
                report=cleaning_report(df),
                ref_values=reference_values(df),
                nicknames_by_ref=nicknames_by_ref,
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
    grp = snapshot.weekly[
        (snapshot.weekly["family"] == family)
        & (snapshot.weekly["price_type"] == price_type)
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

    weekly_sold = family_weekly_series(snapshot, family, "sold")
    weekly_ask = family_weekly_series(snapshot, family, "asking")
    history = [
        {
            "date": r["week"].strftime("%Y-%m-%d"),
            "median": _clean_float(r["median"]),
            "p25": _clean_float(r["p25"]),
            "p75": _clean_float(r["p75"]),
            "n": int(r["n"]),
        }
        for _, r in weekly_sold.iterrows()
    ]
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
            start = r["start_year"]
            end = r["end_year"]
            years = None
            if pd.notna(start):
                years = f"{int(start)}–{int(end) if pd.notna(end) else 'now'}"
            refs.append(
                {
                    "ref": r["ref"],
                    "slug": ref_slug(r["brand"], r["ref"]),
                    "image": ref_image(ref_slug(r["brand"], r["ref"]), slug),
                    "model": r["model"],
                    "years": years,
                    "nicknames": snapshot.nicknames_by_ref.get(r["ref"], []),
                    "n": int(r["n_sold"]),
                    "median": _clean_float(r["median_usd"]),
                    "p25": _clean_float(r["p25_usd"]),
                    "p75": _clean_float(r["p75_usd"]),
                    "retail": _clean_float(r["retail_usd"]),
                    "premium_pct": _clean_float(r["premium_to_retail_pct"]),
                }
            )

    return {
        "brand": row["brand"],
        "family": family,
        "slug": slug,
        "image": family_image(slug),
        "tier": row["tier"],
        "signals": signals_payload_row(row),
        "history": history,
        "asking_history": asking_history,
        "forecast": forecast_payload(snapshot.forecasts.get(family)),
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
    slug = ref_slug(r["brand"], r["ref"])
    return {
        "brand": r["brand"],
        "ref": r["ref"],
        "slug": slug,
        "model": r["model"],
        "family": r["family"],
        "family_slug": fam_slug,
        "years": _years_label(r["start_year"], r["end_year"]),
        "current": pd.isna(r["end_year"]) and pd.notna(r["start_year"]),
        "nicknames": snapshot.nicknames_by_ref.get(r["ref"], []),
        "image": ref_image(slug, fam_slug),
        "n_sold": int(r["n_sold"]),
        "median_usd": _clean_float(r["median_usd"]),
        "p25_usd": _clean_float(r["p25_usd"]),
        "p75_usd": _clean_float(r["p75_usd"]),
        "retail_usd": _clean_float(r["retail_usd"]),
        "premium_pct": _clean_float(r["premium_to_retail_pct"]),
    }


def refs_payload(snapshot: MarketSnapshot) -> list[dict]:
    """Every priced reference — the first-class browse unit."""
    if snapshot.ref_values.empty:
        return []
    return [
        _ref_value_row(snapshot, r) for _, r in snapshot.ref_values.iterrows()
    ]


def ref_detail_payload(snapshot: MarketSnapshot, slug: str) -> dict | None:
    row = snapshot.ref_row(slug)
    if row is None:
        return None
    payload = _ref_value_row(snapshot, row)
    brand, ref, family = row["brand"], row["ref"], row["family"]

    from watchscraper.analysis import REF_VALUE_MIN_CONFIDENCE
    from watchscraper.quant import bootstrap_median_ci

    clean = snapshot.df[snapshot.df["clean"]]
    ref_sold = clean[
        (clean["linked_ref"] == ref)
        & (clean["linked_brand"] == brand)
        & (clean["price_type"] == "sold")
        & (clean["match_confidence"].fillna(0) >= REF_VALUE_MIN_CONFIDENCE)
    ].sort_values("event_date")

    ci_lo, ci_hi = bootstrap_median_ci(ref_sold["price"].values)
    payload["median_ci_lo"] = _clean_float(ci_lo)
    payload["median_ci_hi"] = _clean_float(ci_hi)

    # Individual sales as scatter points — honest at reference sample sizes
    payload["sales_points"] = [
        {
            "date": r["event_date"].strftime("%Y-%m-%d"),
            "value": _clean_float(r["price"]),
            "method": r["match_method"],
        }
        for _, r in ref_sold.iterrows()
    ]

    # Family weekly median as market context
    fam_weekly = family_weekly_series(snapshot, family, "sold")
    payload["family_history"] = [
        {"date": r["week"].strftime("%Y-%m-%d"), "median": _clean_float(r["median"])}
        for _, r in fam_weekly.iterrows()
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

    # Sibling variants: the family's other priced references
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
    """Rank families as purchase candidates.

    Score blends: negative momentum on a non-negative trend ("dip"), low
    volatility (stable value), tight ask/sold spread (liquid exit), and
    discount to dealer ask. It is a screen, not advice.
    """
    rows = []
    for r in signals_payload(snapshot):
        if r["median_usd"] is None or r["n_sold"] < 30:
            continue
        mom = r["momentum_pct"] or 0.0
        vol = r["vol_ann_pct"]
        spread = r["ask_sold_spread_pct"]
        score = 0.0
        reasons = []
        if mom < -3:
            score += min(-mom, 15) / 3
            reasons.append("recent dip")
        if vol is not None and vol < 100:
            score += (100 - vol) / 50
            reasons.append("stable value")
        if spread is not None and 5 <= spread <= 25:
            score += 1.5
            reasons.append("liquid market")
        if spread is not None and spread > 25:
            score += min(spread - 25, 30) / 15
            reasons.append("sold below dealer ask")
        rows.append({**r, "score": round(score, 2), "reasons": reasons})
    rows.sort(key=lambda x: x["score"], reverse=True)
    return rows
