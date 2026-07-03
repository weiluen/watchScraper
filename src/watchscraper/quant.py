"""Quantitative analysis: market index, trend statistics, and forecasts.

Statistical choices, given ~13 weeks of dense weekly data:
  - Medians and Theil-Sen slopes everywhere: listing data is heavy-tailed and
    contaminated; least squares would chase the tails.
  - Mann-Kendall for trend significance: non-parametric, no distributional
    assumptions on 10-15 observations.
  - Bootstrap for every interval: sample sizes are too small and skewed for
    normal-theory intervals.
  - Trend shrinkage in forecasts: a slope fitted on 13 points is noisy, so we
    dampen it toward zero rather than extrapolate it raw.
  - The market index chains the cross-family median of weekly log-returns,
    which tolerates an unbalanced panel (families entering/leaving weeks).
"""

import numpy as np
import pandas as pd
from scipy import stats

TRADING_WEEKS = 52


# ── Market index ──────────────────────────────────────────────────────────


def build_market_index(weekly: pd.DataFrame, price_type: str = "sold") -> pd.Series:
    """Equal-weight watch-market index from weekly medians, rebased 100.

    Chains the median cross-stratum weekly log-return. Strata are
    (family, material) when material is present — a return computed within
    a material bucket cannot be composition drift — and the chaining is
    robust to strata appearing/disappearing week to week.
    """
    columns = (
        ["family", "material"] if "material" in weekly.columns else "family"
    )
    panel = (
        weekly[weekly["price_type"] == price_type]
        .pivot_table(index="week", columns=columns, values="median")
        .sort_index()
    )
    if panel.empty or len(panel) < 2:
        return pd.Series(dtype=float)

    log_returns = np.log(panel).diff()
    index_returns = log_returns.median(axis=1, skipna=True).dropna()
    level = 100.0 * np.exp(index_returns.cumsum())
    first_week = pd.Series([100.0], index=[panel.index[0]])
    return pd.concat([first_week, level]).rename("index")


# ── Trend statistics ──────────────────────────────────────────────────────


def theil_sen_trend(series: pd.Series) -> dict:
    """Robust trend on log-prices. Returns %/month slope with 95% CI."""
    s = series.dropna()
    if len(s) < 4:
        return {"slope_pct_mo": np.nan, "lo_pct_mo": np.nan, "hi_pct_mo": np.nan}
    x = (s.index - s.index[0]).days / 7.0  # weeks
    y = np.log(s.values)
    slope, _, lo, hi = stats.theilslopes(y, x, 0.95)
    to_month = lambda w: (np.exp(w * 52 / 12) - 1) * 100
    return {
        "slope_pct_mo": to_month(slope),
        "lo_pct_mo": to_month(lo),
        "hi_pct_mo": to_month(hi),
    }


def mann_kendall(series: pd.Series) -> float:
    """Mann-Kendall trend test p-value (two-sided, normal approximation)."""
    y = series.dropna().values
    n = len(y)
    if n < 4:
        return np.nan
    s = sum(
        np.sign(y[j] - y[i])
        for i in range(n - 1)
        for j in range(i + 1, n)
    )
    var_s = n * (n - 1) * (2 * n + 5) / 18.0
    if s > 0:
        z = (s - 1) / np.sqrt(var_s)
    elif s < 0:
        z = (s + 1) / np.sqrt(var_s)
    else:
        z = 0.0
    return float(2 * (1 - stats.norm.cdf(abs(z))))


def bootstrap_median_ci(
    prices: np.ndarray, n_boot: int = 2000, seed: int = 42
) -> tuple[float, float]:
    """95% bootstrap CI for a median."""
    if len(prices) < 3:
        return (np.nan, np.nan)
    rng = np.random.default_rng(seed)
    medians = np.median(
        rng.choice(prices, size=(n_boot, len(prices)), replace=True), axis=1
    )
    return (float(np.percentile(medians, 2.5)), float(np.percentile(medians, 97.5)))


# ── Family-level signal table ─────────────────────────────────────────────


def family_signals(
    df: pd.DataFrame,
    weekly: pd.DataFrame,
    dominant: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Per-family quant signal table from clean records + weekly medians.

    Pass the dominant-material weekly frame so trend/volatility/momentum are
    measured within one material stratum (composition-stable); the headline
    median remains the whole family's. `dominant` annotates which stratum
    carried the time-series statistics.

    Columns: liquidity, level (median + bootstrap CI), volatility, momentum,
    robust trend, trend significance, ask/sold spread, premium to retail.
    """
    clean = df[df["clean"]]
    sold = clean[clean["price_type"] == "sold"]
    asking = clean[clean["price_type"] == "asking"]

    rows = []
    for family, grp in sold.groupby("family"):
        brand = grp["brand"].iloc[0]
        prices = grp["price"].values
        median = float(np.median(prices))
        ci_lo, ci_hi = bootstrap_median_ci(prices)

        fam_weekly = (
            weekly[(weekly["family"] == family) & (weekly["price_type"] == "sold")]
            .set_index("week")["median"]
            .sort_index()
        )

        # Volatility: annualized std of weekly log-returns of the median
        log_ret = np.log(fam_weekly).diff().dropna()
        vol_ann = (
            float(log_ret.std(ddof=1) * np.sqrt(TRADING_WEEKS)) * 100
            if len(log_ret) >= 4
            else np.nan
        )

        # Momentum: last 4 weeks vs the prior window
        mom = np.nan
        if len(fam_weekly) >= 8:
            recent = fam_weekly.iloc[-4:].median()
            prior = fam_weekly.iloc[:-4].median()
            mom = (recent / prior - 1) * 100

        trend = theil_sen_trend(fam_weekly)
        mk_p = mann_kendall(fam_weekly)

        # Ask/sold spread: dealer ask premium over realized prices
        fam_ask = asking[asking["family"] == family]["price"]
        spread = (
            (fam_ask.median() / median - 1) * 100 if len(fam_ask) >= 5 else np.nan
        )

        # Premium to retail (only where linked refs carry retail prices)
        linked = grp[grp["retail_price"].notna()]
        premium = (
            ((linked["price"] / linked["retail_price"]).median() - 1) * 100
            if len(linked) >= 5
            else np.nan
        )

        rows.append(
            {
                "brand": brand,
                "family": family,
                "tier": grp["tier"].iloc[0],
                "n_sold": len(prices),
                "median_usd": median,
                "median_ci_lo": ci_lo,
                "median_ci_hi": ci_hi,
                "vol_ann_pct": vol_ann,
                "momentum_pct": mom,
                "trend_pct_mo": trend["slope_pct_mo"],
                "trend_lo": trend["lo_pct_mo"],
                "trend_hi": trend["hi_pct_mo"],
                "mk_pvalue": mk_p,
                "ask_sold_spread_pct": spread,
                "premium_to_retail_pct": premium,
                "n_weeks": len(fam_weekly),
                "dominant_material": (dominant or {}).get(family),
            }
        )
    return pd.DataFrame(rows).sort_values("median_usd", ascending=False)


# ── Forecasting ───────────────────────────────────────────────────────────


def forecast_series(
    series: pd.Series,
    horizon_weeks: int = 8,
    shrink: float = 0.5,
    n_boot: int = 2000,
    seed: int = 42,
) -> pd.DataFrame | None:
    """Shrunk robust-trend forecast with residual-bootstrap intervals.

    Model: log P_t = a + b_shrunk * t + e_t, with b from Theil-Sen and
    b_shrunk = shrink * b. Paths are simulated by resampling historical
    residuals as a random walk around the trend, which widens the interval
    with sqrt(h) — an honest reflection of how little 13 weekly points say
    about week 8.
    """
    s = series.dropna()
    if len(s) < 6:
        return None
    x = (s.index - s.index[0]).days / 7.0
    y = np.log(s.values)
    slope, intercept, _, _ = stats.theilslopes(y, x, 0.95)
    b = shrink * slope
    a = np.median(y - b * x)  # robust intercept given shrunk slope
    resid = y - (a + b * x)

    rng = np.random.default_rng(seed)
    week = pd.Timedelta(weeks=1)
    future_x = x[-1] + np.arange(1, horizon_weeks + 1)
    # Random-walk residual accumulation around the trend line
    steps = rng.choice(np.diff(resid), size=(n_boot, horizon_weeks), replace=True)
    paths = (
        a
        + b * future_x
        + resid[-1]
        + np.cumsum(steps, axis=1)
    )
    prices = np.exp(paths)
    out = pd.DataFrame(
        {
            "week": [s.index[-1] + week * (i + 1) for i in range(horizon_weeks)],
            "forecast": np.exp(a + b * future_x + resid[-1]),
            "p05": np.percentile(prices, 5, axis=0),
            "p25": np.percentile(prices, 25, axis=0),
            "p75": np.percentile(prices, 75, axis=0),
            "p95": np.percentile(prices, 95, axis=0),
        }
    )
    return out


def forecast_families(
    weekly: pd.DataFrame,
    horizon_weeks: int = 8,
    min_weeks: int = 6,
) -> dict[str, pd.DataFrame]:
    """Forecast every family with at least min_weeks of weekly sold medians."""
    forecasts: dict[str, pd.DataFrame] = {}
    sold = weekly[weekly["price_type"] == "sold"]
    for family, grp in sold.groupby("family"):
        s = grp.set_index("week")["median"].sort_index()
        if len(s) >= min_weeks:
            fc = forecast_series(s, horizon_weeks=horizon_weeks)
            if fc is not None:
                forecasts[family] = fc
    return forecasts


# ── Macro overlay ─────────────────────────────────────────────────────────


def macro_correlations(index_series: pd.Series, macro_weekly: pd.DataFrame) -> pd.DataFrame:
    """Correlation of weekly index log-returns with macro factor returns.

    With a short overlap this is descriptive, not inferential — the sample
    size column is the most important one in the output.
    """
    if macro_weekly.empty or index_series.empty:
        return pd.DataFrame()
    idx_ret = np.log(index_series).diff().dropna()
    idx_ret.index = pd.to_datetime(idx_ret.index).tz_localize(None)

    rows = []
    for col in macro_weekly.columns:
        macro_s = macro_weekly[col].dropna()
        # Yields/sentiment are differenced in levels; prices in log-returns
        if col in ("DGS10", "DFII10", "UMCSENT"):
            macro_ret = macro_s.diff().dropna()
        else:
            macro_ret = np.log(macro_s).diff().dropna()
        merged = pd.concat(
            [idx_ret.rename("watch"), macro_ret.rename("macro")], axis=1, join="inner"
        ).dropna()
        n = len(merged)
        if n < 6:
            rows.append({"factor": col, "corr": np.nan, "n_weeks": n, "pvalue": np.nan})
            continue
        corr, p = stats.pearsonr(merged["watch"], merged["macro"])
        rows.append({"factor": col, "corr": corr, "n_weeks": n, "pvalue": p})
    return pd.DataFrame(rows)
