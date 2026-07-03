import numpy as np
import pandas as pd
import pytest

from watchscraper.valuation import (
    build_valuation,
    kernel_median_smoother,
    market_index_from_trends,
    parse_full_set,
)


def make_sales(rows: list[dict]) -> pd.DataFrame:
    base = {
        "price": 10_000.0,
        "family": "Submariner",
        "material": "steel",
        "title": "Rolex Submariner full set",
        "linked_brand": "Rolex",
        "linked_ref": "126610LN",
        "linked_dial": None,
        "match_confidence": 0.95,
        "parsed_attributes": {},
        "retail_price": None,
    }
    records = []
    for r in rows:
        rec = {**base, **r}
        records.append(rec)
    df = pd.DataFrame(records)
    df["event_date"] = pd.to_datetime(df["date"], utc=True)
    return df


def dates(n: int, start="2026-04-01", step_days=3) -> list[str]:
    d0 = pd.Timestamp(start)
    return [(d0 + pd.Timedelta(days=i * step_days)).strftime("%Y-%m-%d") for i in range(n)]


class TestParseFullSet:
    @pytest.mark.parametrize("title,expected", [
        ("Rolex Submariner Box & Papers 2022", True),
        ("Rolex Submariner full set", True),
        ("Rolex 126610LN B&P", True),
        ("Rolex Submariner watch only", False),
        ("Rolex Submariner 2021", False),
    ])
    def test_detection(self, title, expected):
        assert parse_full_set(title) == expected


class TestSmoother:
    def test_flat_data_flat_line(self):
        t = np.arange(0, 90, 3, dtype=float)
        y = np.full_like(t, 2.0)
        grid = np.arange(0, 90, 7, dtype=float)
        s = kernel_median_smoother(t, y, grid, 21.0)
        assert np.allclose(s, 2.0)

    def test_outlier_cannot_bend_line(self):
        t = np.arange(0, 90, 3, dtype=float)
        y = np.full_like(t, 2.0)
        y[15] = 8.0  # one crazy point
        grid = np.arange(0, 90, 7, dtype=float)
        s = kernel_median_smoother(t, y, grid, 21.0)
        assert np.abs(s - 2.0).max() < 0.05


class TestCompositionImmunity:
    def test_mix_shift_does_not_move_value(self):
        # Two variants at stable prices; cheap one sells early, pricey one
        # late. A median-based line would "rally"; the model must not.
        rows = []
        for i, d in enumerate(dates(30)):
            if i < 20:
                rows.append({"date": d, "price": 10_000.0, "linked_dial": "Black",
                             "title": "Sub black dial full set"})
            if i >= 10:
                rows.append({"date": d, "price": 17_000.0, "linked_dial": "Green",
                             "title": "Sub green dial full set"})
        model = build_valuation(make_sales(rows))
        fam = model.families["Submariner"]
        trend_swing = np.exp(fam.trend.max() - fam.trend.min()) - 1
        assert trend_swing < 0.06  # < 6% — a raw median line would show ~40%

    def test_real_common_move_is_captured(self):
        # Both variants drift up 20% together — the trend must see it
        rows = []
        for i, d in enumerate(dates(30)):
            drift = 1.0 + 0.20 * i / 29
            rows.append({"date": d, "price": 10_000.0 * drift, "linked_dial": "Black",
                         "title": "Sub black dial full set"})
            rows.append({"date": d, "price": 17_000.0 * drift, "linked_dial": "Green",
                         "title": "Sub green dial full set"})
        model = build_valuation(make_sales(rows))
        fam = model.families["Submariner"]
        total = np.exp(fam.trend[-1] - fam.trend[0]) - 1
        assert 0.10 < total < 0.30


class TestBorrowingStrength:
    def test_sparse_variant_rides_family_trend(self):
        rows = []
        # Dense black variant with stable price
        for d in dates(40, step_days=2):
            rows.append({"date": d, "price": 10_000.0, "linked_dial": "Black",
                         "title": "Sub black dial full set"})
        # Sparse green variant: only 3 sales, ~70% above black
        for d in ["2026-04-10", "2026-05-10", "2026-06-10"]:
            rows.append({"date": d, "price": 17_000.0, "linked_dial": "Green",
                         "title": "Sub green dial full set"})
        model = build_valuation(make_sales(rows))
        green = model.node_row("Rolex", "126610LN", "Green")
        assert green is not None
        # Shrinkage pulls the 3-sale offset toward family base, but the
        # value must still clearly separate from the black variant
        assert 13_000 < green["value"] < 17_500
        series = model.value_series(green)
        assert len(series) >= 8  # full-length smooth series despite 3 sales

    def test_offset_shrinks_with_tiny_n(self):
        rows = []
        for d in dates(40, step_days=2):
            rows.append({"date": d, "price": 10_000.0, "linked_dial": "Black",
                         "title": "Sub black full set"})
        rows.append({"date": "2026-05-01", "price": 30_000.0, "linked_dial": "Green",
                     "title": "Sub green full set"})
        model = build_valuation(make_sales(rows))
        green = model.node_row("Rolex", "126610LN", "Green")
        # One sale at 3x: kappa = 1/(1+4) = 0.2 → value far below 30k
        assert green["value"] < 15_000


class TestHedonics:
    def test_full_set_premium_recovered(self):
        rows = []
        for i, d in enumerate(dates(40, step_days=2)):
            if i % 2 == 0:
                rows.append({"date": d, "price": 11_000.0,
                             "title": "Rolex Submariner box and papers"})
            else:
                rows.append({"date": d, "price": 10_000.0,
                             "title": "Rolex Submariner watch only"})
        model = build_valuation(make_sales(rows))
        assert "full_set" in model.hedonics
        premium = np.exp(model.hedonics["full_set"]) - 1
        assert 0.05 < premium < 0.15  # true premium is ~10%

    def test_configure_value_removes_full_set(self):
        rows = []
        for i, d in enumerate(dates(40, step_days=2)):
            title = "Sub box and papers" if i % 2 == 0 else "Sub watch only"
            price = 11_000.0 if i % 2 == 0 else 10_000.0
            rows.append({"date": d, "price": price, "title": title})
        model = build_valuation(make_sales(rows))
        naked = model.configure_value(11_000.0, full_set=False)
        assert naked < 11_000.0


class TestForecast:
    def test_damped_and_banded(self):
        rows = []
        for i, d in enumerate(dates(40, step_days=2)):
            rows.append({"date": d, "price": 10_000.0 * (1 + 0.15 * i / 39),
                         "title": "Sub full set"})
        model = build_valuation(make_sales(rows))
        fc = model.forecast_trend("Submariner", horizon_weeks=8)
        assert fc is not None and len(fc) == 8
        # Damped: forecast growth over 8 weeks < recent realized 8-week growth
        fam = model.families["Submariner"]
        recent = fam.trend[-1] - fam.trend[-9] if len(fam.trend) > 9 else 0.1
        projected = fc["trend"].iloc[-1] - fam.trend[-1]
        assert projected < recent
        assert (fc["p95"] > fc["trend"]).all() and (fc["p05"] < fc["trend"]).all()


class TestIndex:
    def test_index_smooth_and_rebased(self):
        rows = []
        for i, d in enumerate(dates(40, step_days=2)):
            rows.append({"date": d, "price": 10_000.0, "title": "Sub full set"})
            rows.append({"date": d, "price": 5_000.0, "family": "Speedmaster",
                         "linked_ref": "310.30.42.50.01.001", "linked_brand": "Omega",
                         "title": "Speedy full set"})
        model = build_valuation(make_sales(rows))
        idx = market_index_from_trends(model)
        assert abs(idx.iloc[0] - 100.0) < 1e-6
        assert idx.max() < 103 and idx.min() > 97  # flat market stays flat
