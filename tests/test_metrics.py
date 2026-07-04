import numpy as np
import pandas as pd
import pytest

from watchscraper.metrics import compute_metrics, peer_rankings, WatchMetrics


class FakeFamily:
    def __init__(self, trend, base=9.5, grid=None):
        self.trend = np.array(trend, dtype=float)
        self.base = base
        self.grid = grid if grid is not None else pd.date_range("2026-04-06", periods=len(trend), freq="W-MON")
        self.n_obs = 100


def node(value=14395.0, chg_1m=-1.0, chg_3m=2.0):
    return pd.Series({"value": value, "chg_1m_pct": chg_1m, "chg_3m_pct": chg_3m})


class TestValueRetention:
    def test_matches_watchcharts_definition(self):
        # WatchCharts confirmed: 14395/11900 - 1 = +21.0%
        m = compute_metrics(node(14395.0), FakeFamily([0.0] * 12), 11900.0, None)
        assert m.value_retention_pct == 21.0

    def test_below_retail_negative(self):
        m = compute_metrics(node(9000.0), FakeFamily([0.0] * 12), 11900.0, None)
        assert m.value_retention_pct < 0


class TestVolatility:
    def test_flat_series_zero_vol(self):
        m = compute_metrics(node(), FakeFamily([0.0] * 12), 10000.0, None)
        assert m.market_volatility_pct == 0.0

    def test_noisy_series_positive_vol(self):
        rng = np.random.default_rng(1)
        trend = np.cumsum(rng.normal(0, 0.02, 20))
        m = compute_metrics(node(), FakeFamily(trend), 10000.0, None)
        assert m.market_volatility_pct > 0


class TestForecastFan:
    def test_three_ordered_scenarios(self):
        trend = np.linspace(0, 0.1, 15)  # steady rise
        m = compute_metrics(node(), FakeFamily(trend), 10000.0, None)
        f = m.forecast_1y
        assert f["conservative"] < f["reasonable"] < f["optimistic"]

    def test_forecast_damped(self):
        # 10% over 15 weeks unannualized ≈ high; damped reasonable must be
        # far below a naive annualized extrapolation
        trend = np.linspace(0, 0.10, 15)
        m = compute_metrics(node(), FakeFamily(trend), 10000.0, None)
        naive_annual = (np.exp(0.10 / 15 * 52) - 1) * 100
        assert m.forecast_1y["reasonable"] < naive_annual


class TestRiskScore:
    def test_range_and_band(self):
        m = compute_metrics(node(), FakeFamily([0.0] * 12), 12000.0,
                            pd.Series(pd.date_range("2025-07-01", periods=50)))
        assert 0 <= m.risk_score <= 100
        assert m.risk_band in ("High Risk", "Moderate Risk", "Low Risk")
        assert set(m.risk_components) == {
            "short_term", "long_term", "liquidity", "predictability", "value_retention"
        }

    def test_falling_illiquid_is_riskier_than_rising_liquid(self):
        rng = np.random.default_rng(3)
        vol_trend = np.cumsum(rng.normal(0, 0.05, 20))
        risky = compute_metrics(
            node(9000.0, chg_1m=-6, chg_3m=-12), FakeFamily(vol_trend), 12000.0,
            pd.Series(pd.date_range("2026-06-01", periods=4)),  # few sales
        )
        safe = compute_metrics(
            node(15000.0, chg_1m=2, chg_3m=6), FakeFamily([0.0] * 20), 10000.0,
            pd.Series(pd.date_range("2025-07-01", periods=120)),  # many sales
        )
        assert risky.risk_score > safe.risk_score


class TestSalesVolume:
    def test_counts_and_inception(self):
        dates = pd.Series(pd.date_range("2025-09-01", periods=40, freq="W"))
        m = compute_metrics(node(), FakeFamily([0.0] * 12), 10000.0, dates)
        assert m.sales_1y == 40
        assert m.market_inception == "Sep 2025"


class TestPeerRankings:
    def test_top_and_bottom(self):
        am = {
            "a": WatchMetrics(value_retention_pct=50, sales_1y=100),
            "b": WatchMetrics(value_retention_pct=10, sales_1y=50),
            "c": WatchMetrics(value_retention_pct=-20, sales_1y=5),
        }
        keys = list(am)
        top = peer_rankings("a", am, keys)
        bottom = peer_rankings("c", am, keys)
        assert top["value_retention"].startswith("Top")
        assert bottom["value_retention"].startswith("Bottom")
