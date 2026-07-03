from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

from watchscraper.analysis import (
    assign_material,
    assign_tiers,
    categorize,
    flag_junk,
    flag_outliers,
    flag_suspect,
    weekly_medians,
)


def make_df(rows: list[dict]) -> pd.DataFrame:
    defaults = {
        "id": 0,
        "source": "ebay",
        "price": 10_000.0,
        "price_type": "sold",
        "condition": "good",
        "title": "Rolex Submariner 126610LN",
        "reference_parsed": None,
        "watch_id": None,
        "query": None,
        "retail_price": None,
        "event_date": pd.Timestamp(datetime(2026, 6, 1, tzinfo=timezone.utc)),
    }
    records = []
    for i, row in enumerate(rows):
        r = {**defaults, **row, "id": i}
        records.append(r)
    return pd.DataFrame(records)


class TestCategorize:
    def test_query_takes_priority_over_title(self):
        df = make_df([{"query": "Rolex Daytona", "title": "some listing mentioning submariner"}])
        out = categorize(df)
        assert out["family"].iloc[0] == "Daytona"
        assert out["brand"].iloc[0] == "Rolex"

    def test_title_fallback_when_no_query(self):
        df = make_df([{"query": None, "title": "Omega Speedmaster Professional Moonwatch"}])
        out = categorize(df)
        assert out["family"].iloc[0] == "Speedmaster"

    def test_offshore_matched_before_royal_oak(self):
        df = make_df([{"query": "Audemars Piguet Royal Oak Offshore"}])
        out = categorize(df)
        assert out["family"].iloc[0] == "Royal Oak Offshore"

    def test_planet_ocean_not_seamaster(self):
        df = make_df([{"query": None, "title": "Omega Seamaster Planet Ocean 600M"}])
        out = categorize(df)
        assert out["family"].iloc[0] == "Planet Ocean"

    def test_unknown_gets_none(self):
        df = make_df([{"query": None, "title": "Seiko 5 automatic"}])
        out = categorize(df)
        assert out["family"].iloc[0] is None


class TestJunkFilter:
    @pytest.mark.parametrize(
        "title",
        [
            "Rolex Submariner box and papers only",
            "Rolex watch box And Original Paper Work Only",
            "Rubber strap for Rolex Submariner 20mm",
            "Bezel insert fits Rolex GMT Master II",
            "Omega x Swatch MoonSwatch Mission to Mars",
            "Rolex Submariner for parts not working",
            "Watch winder for Rolex Omega automatic",
        ],
    )
    def test_junk_flagged(self, title):
        df = flag_junk(make_df([{"title": title}]))
        assert bool(df["is_junk"].iloc[0]), title

    @pytest.mark.parametrize(
        "title",
        [
            "Rolex Submariner 126610LN 2023 with box and papers",
            "Omega Speedmaster Professional full set",
            "Cartier Santos WSSA0018 unworn",
        ],
    )
    def test_real_listings_kept(self, title):
        df = flag_junk(make_df([{"title": title}]))
        assert not bool(df["is_junk"].iloc[0]), title


class TestSuspectFilter:
    def test_sold_far_below_ask_anchor_flagged(self):
        rows = [
            # Dealer asks around 100k
            *[{"price_type": "asking", "price": 100_000.0, "query": "Patek Philippe Nautilus"} for _ in range(6)],
            # A fake "sold" at 5k and a genuine at 80k
            {"price_type": "sold", "price": 5_000.0, "query": "Patek Philippe Nautilus"},
            {"price_type": "sold", "price": 80_000.0, "query": "Patek Philippe Nautilus"},
        ]
        df = categorize(make_df(rows))
        df = flag_junk(df)
        df = flag_suspect(df)
        sold = df[df["price_type"] == "sold"]
        assert bool(sold[sold["price"] == 5_000.0]["is_suspect"].iloc[0])
        assert not bool(sold[sold["price"] == 80_000.0]["is_suspect"].iloc[0])

    def test_asking_records_never_suspect(self):
        rows = [
            *[{"price_type": "asking", "price": 100_000.0, "query": "Patek Philippe Nautilus"} for _ in range(6)],
            {"price_type": "asking", "price": 5_000.0, "query": "Patek Philippe Nautilus"},
        ]
        df = categorize(make_df(rows))
        df = flag_junk(df)
        df = flag_suspect(df)
        assert not df["is_suspect"].any()


class TestOutlierFilter:
    def test_extreme_price_flagged_by_relative_bounds(self):
        prices = [10_000.0] * 10 + [200_000.0]
        rows = [{"price": p, "query": "Rolex Submariner"} for p in prices]
        df = categorize(make_df(rows))
        df = flag_junk(df)
        df = flag_suspect(df)
        df = flag_outliers(df)
        assert bool(df[df["price"] == 200_000.0]["is_outlier"].iloc[0])
        assert not df[df["price"] == 10_000.0]["is_outlier"].any()

    def test_suspects_excluded_from_outlier_stats(self):
        # Without suspect exclusion, a fake-dominated distribution would flag
        # the genuine high sales as outliers.
        rows = [
            *[{"price_type": "asking", "price": 100_000.0, "query": "Patek Philippe Nautilus"} for _ in range(6)],
            *[{"price_type": "sold", "price": 5_000.0, "query": "Patek Philippe Nautilus"} for _ in range(20)],
            *[{"price_type": "sold", "price": 95_000.0, "query": "Patek Philippe Nautilus"} for _ in range(5)],
        ]
        df = categorize(make_df(rows))
        df = flag_junk(df)
        df = flag_suspect(df)
        df = flag_outliers(df)
        genuine = df[(df["price_type"] == "sold") & (df["price"] == 95_000.0)]
        assert not genuine["is_outlier"].any()


class TestTiersAndWeekly:
    def _clean_df(self, rows):
        df = categorize(make_df(rows))
        df = assign_material(df)
        df = flag_junk(df)
        df = flag_suspect(df)
        df = flag_outliers(df)
        df["clean"] = (
            ~df["is_junk"] & ~df["is_outlier"] & ~df["is_suspect"] & df["family"].notna()
        )
        return df

    def test_tier_from_family_median(self):
        rows = [{"price": 100_000.0, "query": "Patek Philippe Nautilus"} for _ in range(5)]
        df = assign_tiers(self._clean_df(rows))
        assert df["tier"].iloc[0] == "ultra"

    def test_weekly_medians_drop_thin_buckets(self):
        base = pd.Timestamp(datetime(2026, 6, 1, tzinfo=timezone.utc))
        rows = [
            *[
                {"price": 10_000.0 + i, "query": "Rolex Submariner", "event_date": base}
                for i in range(6)
            ],
            # Only 2 observations the following week — should be dropped
            {"price": 10_000.0, "query": "Rolex Submariner", "event_date": base + pd.Timedelta(weeks=1)},
            {"price": 10_500.0, "query": "Rolex Submariner", "event_date": base + pd.Timedelta(weeks=1)},
        ]
        df = self._clean_df(rows)
        weekly = weekly_medians(df, min_n=5)
        assert len(weekly) == 1
        assert weekly["n"].iloc[0] == 6
