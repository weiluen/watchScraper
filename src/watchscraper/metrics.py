"""WatchCharts-style market metrics, computed from our valuation model.

Reverse-engineered from watchcharts.com (see docs/watchcharts_taxonomy.md).
Each metric mirrors a WatchCharts definition, computed off the hierarchical
smoothed value series and the clean sold corpus rather than raw medians:

  value_retention   = market value / retail − 1                (their exact def)
  market_volatility = std of weekly log-returns of the smoothed value
  1y_sales_volume   = count of clean sold obs, trailing ~year (their demand proxy)
  risk_score /100   = composite of five 0–1 sub-scores, higher = riskier:
                        short-term perf, long-term perf, liquidity,
                        predictability (inverse volatility), value retention
  forecast fan      = optimistic / reasonable / conservative 1y % change,
                        the damped trend widened into scenarios by volatility
  market_inception  = first observed sale date
  peer rankings     = percentile of each metric within brand / family
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

WEEKS_PER_YEAR = 52


@dataclass
class WatchMetrics:
    value_retention_pct: float | None = None
    market_volatility_pct: float | None = None
    risk_score: int | None = None
    risk_band: str | None = None
    risk_components: dict = field(default_factory=dict)
    sales_1y: int | None = None
    market_inception: str | None = None
    forecast_1y: dict = field(default_factory=dict)  # optimistic/reasonable/conservative


def _annualized_vol_pct(trend: np.ndarray) -> float | None:
    """Std of weekly log-returns of the smoothed value, as a percent.

    WatchCharts shows a single-digit % (4.4%); the smoothed series' weekly
    return std is the natural analogue, not annualized (annualizing a
    grey-market series exaggerates it).
    """
    if trend is None or len(trend) < 4:
        return None
    returns = np.diff(trend)  # trend is already log-space deviations
    return float(np.std(returns, ddof=1) * 100)


def _sub_score(value: float, lo: float, hi: float, invert: bool = False) -> float:
    """Clamp a value to a 0–1 risk contribution. invert=True means high
    input → low risk."""
    if value is None or np.isnan(value):
        return 0.5
    x = (value - lo) / (hi - lo) if hi != lo else 0.5
    x = max(0.0, min(1.0, x))
    return 1.0 - x if invert else x


def compute_metrics(
    node: pd.Series | None,
    fam_model,
    retail_usd: float | None,
    sold_dates: pd.Series | None,
    reference_date: pd.Timestamp | None = None,
) -> WatchMetrics:
    """Compute the metric suite for one watch node.

    node: a row from ValuationModel.nodes (value, offset, chg_1m/3m).
    fam_model: the node's FamilyModel (base, trend, grid).
    sold_dates: event_dates of this watch's clean sold obs (for volume/inception).
    """
    m = WatchMetrics()
    if node is None or fam_model is None:
        return m

    value = float(node["value"])

    # ── Value retention ──
    if retail_usd:
        m.value_retention_pct = round((value / retail_usd - 1) * 100, 1)

    # ── Volatility ──
    vol = _annualized_vol_pct(fam_model.trend)
    m.market_volatility_pct = round(vol, 1) if vol is not None else None

    # ── Sales volume + inception (trailing ~year of our window) ──
    if sold_dates is not None and len(sold_dates):
        m.sales_1y = int(len(sold_dates))
        m.market_inception = pd.to_datetime(sold_dates.min()).strftime("%b %Y")

    # ── Forecast fan: damp the smoothed trend's recent slope, widen by vol ──
    if len(fam_model.trend) >= 6:
        from scipy import stats

        tail = min(10, len(fam_model.trend))
        slope, _, _, _ = stats.theilslopes(
            fam_model.trend[-tail:], np.arange(tail, dtype=float), 0.90
        )
        reasonable = slope * 0.4 * WEEKS_PER_YEAR  # damped, annualized (log)
        # Scenario spread from volatility, floored: a 1-year forecast always
        # carries real uncertainty even when the fitted line looks smooth.
        vol_frac = max(vol / 100 if vol else 0.0, 0.02)
        band = vol_frac * np.sqrt(WEEKS_PER_YEAR)
        m.forecast_1y = {
            "optimistic": round((np.exp(reasonable + band) - 1) * 100, 1),
            "reasonable": round((np.exp(reasonable) - 1) * 100, 1),
            "conservative": round((np.exp(reasonable - band) - 1) * 100, 1),
        }

    # ── Risk score: composite, higher = riskier short-term ──
    chg_1m = node.get("chg_1m_pct")
    chg_3m = node.get("chg_3m_pct")
    # Short-term performance risk: falling price = higher risk
    short = _sub_score(chg_1m if pd.notna(chg_1m) else 0.0, -8, 4, invert=True)
    long = _sub_score(chg_3m if pd.notna(chg_3m) else 0.0, -15, 10, invert=True)
    # Liquidity risk: fewer sales = higher risk
    liquidity = _sub_score(m.sales_1y or 0, 3, 120, invert=True)
    # Predictability: high volatility = higher risk
    predictability = _sub_score(vol if vol is not None else 5.0, 1.0, 10.0)
    # Value-retention risk: trading below retail = higher risk
    retention_risk = _sub_score(m.value_retention_pct or 0.0, -30, 60, invert=True)

    weights = {
        "short_term": 0.25, "long_term": 0.20, "liquidity": 0.20,
        "predictability": 0.20, "value_retention": 0.15,
    }
    parts = {
        "short_term": short, "long_term": long, "liquidity": liquidity,
        "predictability": predictability, "value_retention": retention_risk,
    }
    score = sum(weights[k] * parts[k] for k in weights)
    m.risk_score = int(round(score * 100))
    m.risk_band = (
        "High Risk" if m.risk_score >= 60
        else "Moderate Risk" if m.risk_score >= 35
        else "Low Risk"
    )
    m.risk_components = {k: round(v, 2) for k, v in parts.items()}
    return m


def peer_rankings(
    watch_key: str, all_metrics: dict[str, WatchMetrics], group_keys: list[str]
) -> dict[str, str]:
    """Percentile rank of each metric within a peer group.

    all_metrics: watch_key -> WatchMetrics for the peer set.
    Returns e.g. {"value_retention": "Top 17%", ...}.
    """
    if watch_key not in all_metrics:
        return {}
    fields = {
        "market_volatility": ("market_volatility_pct", False),
        "value_retention": ("value_retention_pct", True),
        "risk_score": ("risk_score", False),
        "sales_volume": ("sales_1y", True),
    }
    out = {}
    for label, (attr, higher_better) in fields.items():
        vals = [
            getattr(all_metrics[k], attr)
            for k in group_keys
            if getattr(all_metrics[k], attr, None) is not None
        ]
        mine = getattr(all_metrics[watch_key], attr, None)
        if mine is None or len(vals) < 3:
            continue
        below = sum(1 for v in vals if v < mine) / len(vals)
        pct = below if higher_better else (1 - below)
        rank = int(round((1 - pct) * 100))
        out[label] = f"Top {max(rank,1)}%" if rank <= 50 else f"Bottom {101-rank}%"
    return out
