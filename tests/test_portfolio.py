from datetime import date

import pandas as pd
import pytest

from watchscraper.web.portfolio import build_family_value_panel, value_holdings


def make_weekly() -> pd.DataFrame:
    weeks = pd.date_range("2026-04-06", periods=4, freq="W-MON")
    rows = []
    for i, w in enumerate(weeks):
        rows.append(
            {"brand": "Rolex", "family": "Submariner", "price_type": "sold",
             "week": w, "median": 10_000.0 + i * 500, "n": 10}
        )
        rows.append(
            {"brand": "Omega", "family": "Speedmaster", "price_type": "sold",
             "week": w, "median": 4_000.0, "n": 10}
        )
        # Asking rows must be ignored by valuation
        rows.append(
            {"brand": "Rolex", "family": "Submariner", "price_type": "asking",
             "week": w, "median": 99_999.0, "n": 10}
        )
    return pd.DataFrame(rows)


def holding(**kw) -> dict:
    base = {
        "id": 1, "nickname": None, "brand": "Rolex", "family": "Submariner",
        "reference_number": None, "purchase_price_usd": None,
        "purchase_date": None, "condition": None, "notes": None,
    }
    return {**base, **kw}


class TestValueHoldings:
    def test_current_value_is_latest_sold_median(self):
        out = value_holdings([holding()], make_weekly())
        h = out["holdings"][0]
        assert h["current_value"] == 11_500.0  # last week's sold median
        assert h["priced"]

    def test_gain_vs_purchase(self):
        out = value_holdings(
            [holding(purchase_price_usd=10_000.0, purchase_date=date(2026, 1, 1))],
            make_weekly(),
        )
        h = out["holdings"][0]
        assert h["gain_usd"] == 1_500.0
        assert h["gain_pct"] == pytest.approx(15.0)

    def test_portfolio_series_sums_families(self):
        out = value_holdings(
            [holding(), holding(id=2, brand="Omega", family="Speedmaster")],
            make_weekly(),
        )
        assert out["totals"]["value"] == 11_500.0 + 4_000.0
        # Series present and summed for every common week
        assert len(out["series"]) == 4
        assert out["series"][0]["value"] == 10_000.0 + 4_000.0

    def test_unknown_family_is_unpriced_not_crash(self):
        out = value_holdings(
            [holding(family="Moonphase Fantasy", brand="Acme")], make_weekly()
        )
        h = out["holdings"][0]
        assert h["current_value"] is None
        assert not h["priced"]
        assert out["totals"]["n_priced"] == 0

    def test_allocation_by_brand(self):
        out = value_holdings(
            [holding(), holding(id=2, brand="Omega", family="Speedmaster")],
            make_weekly(),
        )
        labels = {a["label"] for a in out["allocation"]}
        assert labels == {"Rolex", "Omega"}
        rolex = next(a for a in out["allocation"] if a["label"] == "Rolex")
        assert rolex["value"] == 11_500.0

    def test_empty_portfolio(self):
        out = value_holdings([], make_weekly())
        assert out["totals"]["value"] is None
        assert out["series"] == []
        assert out["allocation"] == []


class TestPanel:
    def test_asking_excluded(self):
        panel = build_family_value_panel(make_weekly())
        assert panel["Submariner"].max() == 11_500.0
