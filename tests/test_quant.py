import numpy as np
import pandas as pd
import pytest

from watchscraper.quant import (
    build_market_index,
    forecast_series,
    mann_kendall,
    theil_sen_trend,
)


def weekly_index(n: int) -> pd.DatetimeIndex:
    return pd.date_range("2026-03-30", periods=n, freq="W-MON")


class TestTheilSen:
    def test_recovers_known_trend(self):
        # 2% weekly growth in log space
        idx = weekly_index(13)
        prices = pd.Series(10_000 * np.exp(0.02 * np.arange(13)), index=idx)
        trend = theil_sen_trend(prices)
        expected_monthly = (np.exp(0.02 * 52 / 12) - 1) * 100
        assert trend["slope_pct_mo"] == pytest.approx(expected_monthly, rel=0.05)

    def test_flat_series_zero_slope(self):
        idx = weekly_index(13)
        prices = pd.Series([10_000.0] * 13, index=idx)
        trend = theil_sen_trend(prices)
        assert trend["slope_pct_mo"] == pytest.approx(0.0, abs=1e-9)

    def test_too_short_returns_nan(self):
        idx = weekly_index(3)
        prices = pd.Series([1.0, 2.0, 3.0], index=idx)
        assert np.isnan(theil_sen_trend(prices)["slope_pct_mo"])


class TestMannKendall:
    def test_monotone_series_significant(self):
        s = pd.Series(np.arange(13, dtype=float), index=weekly_index(13))
        assert mann_kendall(s) < 0.01

    def test_noise_not_significant(self):
        rng = np.random.default_rng(7)
        s = pd.Series(rng.normal(0, 1, 13), index=weekly_index(13))
        assert mann_kendall(s) > 0.05


class TestMarketIndex:
    def test_balanced_panel_tracks_common_growth(self):
        idx = weekly_index(10)
        weekly = pd.concat(
            [
                pd.DataFrame(
                    {
                        "brand": "B",
                        "family": fam,
                        "price_type": "sold",
                        "week": idx,
                        "median": base * np.exp(0.01 * np.arange(10)),
                        "n": 10,
                    }
                )
                for fam, base in [("A", 5_000), ("B", 20_000)]
            ]
        )
        index = build_market_index(weekly)
        assert index.iloc[0] == pytest.approx(100.0)
        # 9 weeks of 1% log growth
        assert index.iloc[-1] == pytest.approx(100 * np.exp(0.09), rel=0.01)

    def test_unbalanced_panel_no_composition_jump(self):
        idx = weekly_index(10)
        flat = pd.DataFrame(
            {
                "brand": "B",
                "family": "A",
                "price_type": "sold",
                "week": idx,
                "median": [5_000.0] * 10,
                "n": 10,
            }
        )
        # Expensive family only present in the second half — a naive
        # level-average index would jump on entry; a chained-return index must not.
        late = pd.DataFrame(
            {
                "brand": "B",
                "family": "B",
                "price_type": "sold",
                "week": idx[5:],
                "median": [50_000.0] * 5,
                "n": 10,
            }
        )
        index = build_market_index(pd.concat([flat, late]))
        assert index.max() == pytest.approx(100.0)
        assert index.min() == pytest.approx(100.0)


class TestForecast:
    def test_shapes_and_monotone_uncertainty(self):
        idx = weekly_index(13)
        rng = np.random.default_rng(3)
        prices = pd.Series(
            10_000 * np.exp(0.01 * np.arange(13) + rng.normal(0, 0.02, 13)), index=idx
        )
        fc = forecast_series(prices, horizon_weeks=8)
        assert fc is not None
        assert len(fc) == 8
        band_start = fc["p95"].iloc[0] - fc["p05"].iloc[0]
        band_end = fc["p95"].iloc[-1] - fc["p05"].iloc[-1]
        assert band_end > band_start  # uncertainty must widen with horizon
        assert (fc["p05"] <= fc["forecast"]).all()
        assert (fc["forecast"] <= fc["p95"]).all()

    def test_too_short_returns_none(self):
        idx = weekly_index(4)
        prices = pd.Series([1.0, 2.0, 3.0, 4.0], index=idx)
        assert forecast_series(prices) is None

    def test_shrinkage_dampens_extrapolation(self):
        idx = weekly_index(13)
        prices = pd.Series(10_000 * np.exp(0.05 * np.arange(13)), index=idx)
        fc_raw = forecast_series(prices, shrink=1.0)
        fc_shrunk = forecast_series(prices, shrink=0.5)
        assert fc_shrunk["forecast"].iloc[-1] < fc_raw["forecast"].iloc[-1]
