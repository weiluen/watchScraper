from datetime import date

import pandas as pd
import pytest

from watchscraper.web.portfolio import value_holdings


def make_weekly() -> pd.DataFrame:
    weeks = pd.date_range("2026-04-06", periods=4, freq="W-MON")
    rows = []
    for i, w in enumerate(weeks):
        rows.append(
            {"brand": "Rolex", "family": "Submariner", "price_type": "sold",
             "week": w, "median": 10_000.0 + i * 500, "n": 10}
        )
    return pd.DataFrame(rows)


def make_ref_values() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"brand": "Rolex", "ref": "116610LV", "family": "Submariner",
             "median_usd": 17_250.0},
            {"brand": "Rolex", "ref": "126610LN", "family": "Submariner",
             "median_usd": 11_499.0},
        ]
    )


def holding(**kw) -> dict:
    base = {
        "id": 1, "nickname": None, "brand": "Rolex", "family": "Submariner",
        "reference_number": None, "purchase_price_usd": None,
        "purchase_date": None, "condition": None, "notes": None,
    }
    return {**base, **kw}


class TestReferenceValuation:
    def test_ref_holding_valued_at_variant(self):
        out = value_holdings(
            [holding(reference_number="116610LV")],
            make_weekly(),
            ref_values=make_ref_values(),
        )
        h = out["holdings"][0]
        assert h["current_value"] == 17_250.0  # the Hulk's value, not the family's
        assert h["priced_at"] == "reference"

    def test_ref_series_scaled_to_variant_level(self):
        out = value_holdings(
            [holding(reference_number="116610LV")],
            make_weekly(),
            ref_values=make_ref_values(),
        )
        series = out["holdings"][0]["series"]
        # Last point equals the variant value; earlier points keep the
        # family's trend shape scaled to the variant level
        assert series[-1]["value"] == pytest.approx(17_250.0)
        family_ratio = 10_000.0 / 11_500.0
        assert series[0]["value"] == pytest.approx(17_250.0 * family_ratio)

    def test_unpriced_ref_falls_back_to_family(self):
        out = value_holdings(
            [holding(reference_number="999999ZZ")],
            make_weekly(),
            ref_values=make_ref_values(),
        )
        h = out["holdings"][0]
        assert h["current_value"] == 11_500.0  # family weekly median
        assert h["priced_at"] == "family"

    def test_no_ref_prices_at_family(self):
        out = value_holdings(
            [holding()], make_weekly(), ref_values=make_ref_values()
        )
        assert out["holdings"][0]["priced_at"] == "family"

    def test_mixed_portfolio_totals(self):
        out = value_holdings(
            [holding(reference_number="116610LV"), holding(id=2)],
            make_weekly(),
            ref_values=make_ref_values(),
        )
        assert out["totals"]["value"] == 17_250.0 + 11_500.0


class TestConditionAdjustment:
    """Holdings marked for their condition and completeness (P14)."""

    def _weekly(self):
        weeks = pd.date_range("2026-04-06", periods=4, freq="W-MON")
        return pd.DataFrame([
            {"brand": "Rolex", "family": "Submariner", "price_type": "sold",
             "week": w, "median": 11_000.0, "n": 10} for w in weeks
        ])

    def test_new_watch_only_moves_value(self):
        from watchscraper.web.portfolio import value_holdings

        rv = pd.DataFrame([{"brand": "Rolex", "ref": "126610LN", "family": "Submariner",
                            "median_usd": 11_000.0}])
        base = value_holdings(
            [holding(reference_number="126610LN", condition="good", contents="full_set")],
            self._weekly(), ref_values=rv)["holdings"][0]["current_value"]
        adjusted = value_holdings(
            [holding(reference_number="126610LN", condition="new", contents="watch_only")],
            self._weekly(), ref_values=rv)["holdings"][0]["current_value"]
        # new (+) but watch-only (−); watch-only dominates → net below base
        assert adjusted is not None and base is not None
        assert adjusted < base
