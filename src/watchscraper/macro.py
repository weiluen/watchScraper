"""Macro market data from FRED (no API key required).

Watches are long-duration, zero-yield collectible assets. The factors below
are the standard suspects for luxury-collectible pricing:

  SP500     — equity wealth effect / risk appetite
  NASDAQCOM — tech wealth (over-represented among watch buyers)
  DGS10     — 10Y nominal yield
  DFII10    — 10Y TIPS real yield (the 2022-23 watch-market crash tracked the
              real-rate shock almost one-for-one)
  DTWEXBGS  — broad USD index (watches are a global market priced in USD)
  CPIAUCSL  — CPI, the inflation-hedge narrative
  UMCSENT   — consumer sentiment
  CBBTCUSD  — Bitcoin, proxy for the crypto-wealth channel that fueled the
              2020-22 watch bubble
"""

import io
import logging
from datetime import date

import pandas as pd
import requests
from sqlalchemy import text

logger = logging.getLogger(__name__)

FRED_SERIES: dict[str, str] = {
    "SP500": "S&P 500",
    "NASDAQCOM": "NASDAQ Composite",
    "DGS10": "10Y Treasury Yield",
    "DFII10": "10Y Real Yield (TIPS)",
    "DTWEXBGS": "Broad USD Index",
    "CPIAUCSL": "CPI (All Urban)",
    "UMCSENT": "Consumer Sentiment",
    "CBBTCUSD": "Bitcoin (Coinbase)",
}

FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"


def fetch_series(series_id: str) -> pd.DataFrame:
    """Fetch one FRED series as a (date, value) DataFrame."""
    resp = requests.get(FRED_CSV_URL.format(series_id=series_id), timeout=30)
    resp.raise_for_status()
    df = pd.read_csv(io.StringIO(resp.text))
    df.columns = ["date", "value"]
    df["date"] = pd.to_datetime(df["date"]).dt.date
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["value"])
    df["series_id"] = series_id
    return df


def store_series(engine, df: pd.DataFrame) -> int:
    """Upsert macro observations; returns rows written."""
    if df.empty:
        return 0
    rows = df[["series_id", "date", "value"]].to_dict("records")
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO macro_series (series_id, date, value)
                VALUES (:series_id, :date, :value)
                ON CONFLICT (series_id, date)
                DO UPDATE SET value = EXCLUDED.value
            """),
            rows,
        )
    return len(rows)


def fetch_all(engine, since: date | None = None) -> dict[str, int]:
    """Fetch and store every configured FRED series."""
    counts: dict[str, int] = {}
    for series_id in FRED_SERIES:
        try:
            df = fetch_series(series_id)
            if since is not None:
                df = df[df["date"] >= since]
            counts[series_id] = store_series(engine, df)
            logger.info("%s: %d observations", series_id, counts[series_id])
        except Exception:
            logger.exception("Failed to fetch %s", series_id)
            counts[series_id] = 0
    return counts


def load_weekly(engine) -> pd.DataFrame:
    """Macro series resampled to weekly (Monday-start, last observation)."""
    df = pd.read_sql(text("SELECT series_id, date, value FROM macro_series"), engine)
    if df.empty:
        return pd.DataFrame()
    df["date"] = pd.to_datetime(df["date"])
    wide = df.pivot_table(index="date", columns="series_id", values="value")
    weekly = wide.resample("W-MON", label="left", closed="left").last()
    return weekly.ffill()
