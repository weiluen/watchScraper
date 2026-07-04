"""Portfolio valuation: mark holdings to market, reference-first.

Valuation is conservative and transparent:
  - A holding pinned to a priced reference is valued at that reference's
    median sold price — the variant's own market value. Its time series is
    the family's weekly median scaled by the reference-to-family value
    ratio (references rarely have enough weekly sales for their own series;
    the family carries the trend, the ratio carries the variant level).
  - A holding with no reference (or an unpriced one) falls back to the
    family weekly median.
  - No condition or full-set adjustment is applied — the median is the
    honest mid-market mark for an unspecified example.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class HoldingValuation:
    holding_id: int
    current_value: float | None
    purchase_price: float | None
    gain_usd: float | None
    gain_pct: float | None
    series: list[dict]  # weekly {date, value}


_CONDITION_MULT = {
    "new": 1.04, "unworn": 1.04, "excellent": 1.015, "good": 1.0, "fair": 0.92,
}


def _json_float(v) -> float | None:
    if v is None:
        return None
    f = float(v)
    return None if (np.isnan(f) or np.isinf(f)) else f


def build_family_value_panel(weekly: pd.DataFrame) -> pd.DataFrame:
    """Wide weekly panel of family median sold prices, forward-filled."""
    sold = weekly[weekly["price_type"] == "sold"]
    if sold.empty:
        return pd.DataFrame()
    panel = sold.pivot_table(index="week", columns="family", values="median")
    return panel.sort_index().ffill()


def value_holdings(
    holdings: list[dict],
    weekly: pd.DataFrame,
    ref_values: pd.DataFrame | None = None,
    valuation=None,
) -> dict:
    """Value each holding and the whole portfolio over time.

    holdings: [{id, family, reference_number?, dial_variant?, ...}]
    valuation: the hierarchical ValuationModel — when present, every holding
    is marked from its node's smooth value series (variant → reference →
    family-generic), which is the composition-adjusted estimate.
    Falls back to weekly-median panels when no model is supplied.
    """
    panel = build_family_value_panel(weekly)

    ref_median: dict[tuple[str, str, str], float] = {}
    if ref_values is not None and not ref_values.empty:
        for _, r in ref_values.iterrows():
            if pd.isna(r["median_usd"]):
                continue
            dial = r.get("dial_variant")
            dial = dial if (dial and pd.notna(dial)) else ""
            ref_median[(r["brand"], r["ref"], dial)] = float(r["median_usd"])

    per_holding = []
    portfolio_series: pd.Series | None = None

    for h in holdings:
        family = h["family"]
        series = panel[family].dropna() if family in panel.columns else pd.Series(dtype=float)
        ref = h.get("reference_number")
        dial = h.get("dial_variant") or ""
        priced_at = "family"

        node = None
        if valuation is not None:
            node = valuation.node_row(h["brand"], ref or None, dial or None, family)
        if node is not None:
            node_series = valuation.value_series(node)
            if len(node_series):
                series = node_series
                priced_at = (
                    "reference" if node["node_type"] in ("variant", "ref") else "family"
                )
        else:
            # Legacy path: variant value scales the family weekly panel
            ref_val = ref_median.get((h["brand"], ref, dial)) if ref else None
            if ref_val is not None and len(series) and series.iloc[-1] > 0:
                series = series * (ref_val / float(series.iloc[-1]))
                priced_at = "reference"
            elif ref_val is not None:
                series = pd.Series([ref_val])  # value known, no trend series
                priced_at = "reference"

        # Condition + completeness hedonic adjustment on the mark (the model
        # values at full-set/good; a holding's own state moves its value).
        cond_m = _CONDITION_MULT.get(h.get("condition") or "good", 1.0)
        fs = valuation.hedonics.get("full_set", 0.12) if valuation is not None else 0.12
        watch_only = 1.0 / np.exp(fs)
        cont_m = {
            "full_set": 1.0,
            "with_papers": 1.0 - (1.0 - watch_only) * 0.4,
            "with_box": 1.0 - (1.0 - watch_only) * 0.6,
            "watch_only": watch_only,
        }.get(h.get("contents") or "full_set", 1.0)
        adj = cond_m * cont_m
        if len(series):
            series = series * adj

        current = _json_float(series.iloc[-1]) if len(series) else None
        purchase = _json_float(h.get("purchase_price_usd"))
        gain = gain_pct = None
        if current is not None and purchase:
            gain = current - purchase
            gain_pct = (current / purchase - 1) * 100
        per_holding.append(
            {
                "id": h["id"],
                "nickname": h.get("nickname"),
                "brand": h["brand"],
                "family": family,
                "reference_number": h.get("reference_number"),
                "dial_variant": h.get("dial_variant"),
                "condition": h.get("condition"),
                "contents": h.get("contents"),
                "purchase_price_usd": purchase,
                "purchase_date": (
                    h["purchase_date"].isoformat() if h.get("purchase_date") else None
                ),
                "current_value": current,
                "gain_usd": _json_float(gain),
                "gain_pct": _json_float(gain_pct),
                "priced_at": priced_at if current is not None else None,
                "series": [
                    {"date": idx.strftime("%Y-%m-%d"), "value": _json_float(v)}
                    for idx, v in series.items()
                    if not isinstance(idx, int)
                ],
                "priced": current is not None,
            }
        )
        if len(series) and not isinstance(series.index[0], int):
            portfolio_series = (
                series if portfolio_series is None else portfolio_series.add(series, fill_value=None)
            )

    # Portfolio series only spans weeks where every priced family has a value;
    # add(fill_value=None) leaves NaN where any component is missing, which we
    # drop rather than misrepresent a partial sum as the whole portfolio.
    series_points = []
    if portfolio_series is not None:
        for idx, v in portfolio_series.dropna().items():
            series_points.append({"date": idx.strftime("%Y-%m-%d"), "value": _json_float(v)})

    priced = [h for h in per_holding if h["priced"]]
    total_value = sum(h["current_value"] for h in priced) if priced else None
    total_cost = sum(
        h["purchase_price_usd"] for h in priced if h["purchase_price_usd"]
    )
    with_cost = [h for h in priced if h["purchase_price_usd"]]
    total_gain = (
        sum(h["current_value"] - h["purchase_price_usd"] for h in with_cost)
        if with_cost
        else None
    )

    # Allocation by brand for the donut (≤6 segments; tail folds into Other)
    allocation: list[dict] = []
    if priced:
        by_brand: dict[str, float] = {}
        for h in priced:
            by_brand[h["brand"]] = by_brand.get(h["brand"], 0.0) + h["current_value"]
        ranked = sorted(by_brand.items(), key=lambda kv: kv[1], reverse=True)
        head, tail = ranked[:5], ranked[5:]
        allocation = [{"label": b, "value": round(v, 2)} for b, v in head]
        if tail:
            allocation.append(
                {"label": "Other", "value": round(sum(v for _, v in tail), 2)}
            )

    return {
        "holdings": per_holding,
        "series": series_points,
        "totals": {
            "value": _json_float(total_value),
            "cost": _json_float(total_cost) if with_cost else None,
            "gain_usd": _json_float(total_gain),
            "gain_pct": _json_float(
                (total_gain / total_cost * 100) if total_gain is not None and total_cost else None
            ),
            "n_holdings": len(per_holding),
            "n_priced": len(priced),
        },
        "allocation": allocation,
    }
