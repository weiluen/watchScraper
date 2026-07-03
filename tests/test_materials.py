import pandas as pd
import pytest

from watchscraper.analysis import (
    assign_material,
    categorize,
    dominant_material,
    dominant_weekly,
    flag_junk,
    flag_suspect,
)
from watchscraper.quant import build_market_index
from tests.test_analysis import make_df


class TestAssignMaterial:
    def test_linked_material_is_authoritative(self):
        df = make_df([{"title": "some watch"}])
        df["linked_material"] = ["Rolesor"]
        df["parsed_material"] = ["steel"]  # title says steel; catalog says two-tone
        out = assign_material(df)
        assert out["material"].iloc[0] == "two-tone"

    def test_parsed_material_fallback(self):
        df = make_df([{"title": "Rolex Datejust Two-Tone"}])
        df["linked_material"] = [None]
        df["parsed_material"] = ["two-tone"]
        out = assign_material(df)
        assert out["material"].iloc[0] == "two-tone"

    def test_unstated_defaults_to_steel(self):
        df = make_df([{"title": "Rolex Datejust 41 blue dial"}])
        df["linked_material"] = [None]
        df["parsed_material"] = [None]
        out = assign_material(df)
        assert out["material"].iloc[0] == "steel"

    @pytest.mark.parametrize(
        "raw,bucket",
        [
            ("Oystersteel", "steel"),
            ("White Gold", "precious"),
            ("Everose Gold", "precious"),
            ("Platinum", "precious"),
            ("Titanium", "other"),
            ("Steel/Sedna Gold", "two-tone"),
            ("Oystersteel/White Gold", "two-tone"),
        ],
    )
    def test_bucket_classification(self, raw, bucket):
        df = make_df([{"title": "x"}])
        df["linked_material"] = [raw]
        df["parsed_material"] = [None]
        assert assign_material(df)["material"].iloc[0] == bucket


class TestMaterialAwareAnchor:
    def test_gold_fake_caught_by_stratum_anchor(self):
        # Steel Datejusts ask ~12k; gold ones ~35k. A $10k "gold" sold is
        # 29% of the gold anchor (suspect) but 83% of the steel anchor —
        # only the stratified anchor catches it.
        rows = [
            *[{"price_type": "asking", "price": 12_000.0, "query": "Rolex Datejust"}
              for _ in range(6)],
            *[{"price_type": "asking", "price": 35_000.0,
               "title": "Rolex Datejust 41 Yellow Gold", "query": "Rolex Datejust"}
              for _ in range(6)],
            {"price_type": "sold", "price": 10_000.0,
             "title": "Rolex Datejust 18k Yellow Gold", "query": "Rolex Datejust"},
        ]
        df = categorize(make_df(rows))
        df["linked_material"] = None
        df["parsed_material"] = [
            None] * 6 + ["yellow-gold"] * 6 + ["yellow-gold"]
        df = assign_material(df)
        df = flag_junk(df)
        df = flag_suspect(df)
        sold = df[df["price_type"] == "sold"]
        assert bool(sold["is_suspect"].iloc[0])


class TestDominantStratum:
    def _weekly(self):
        weeks = pd.date_range("2026-04-06", periods=3, freq="W-MON")
        rows = []
        for w in weeks:
            rows.append({"brand": "Rolex", "family": "Datejust", "material": "steel",
                         "price_type": "sold", "week": w, "median": 12_000.0, "n": 10})
            rows.append({"brand": "Rolex", "family": "Datejust", "material": "two-tone",
                         "price_type": "sold", "week": w, "median": 17_000.0, "n": 4})
        return pd.DataFrame(rows)

    def test_dominant_material_by_volume(self):
        rows = (
            [{"query": "Rolex Datejust", "price": 12_000.0} for _ in range(6)]
            + [{"query": "Rolex Datejust", "price": 17_000.0,
                "title": "Rolex Datejust Two-Tone"} for _ in range(2)]
        )
        df = categorize(make_df(rows))
        df["linked_material"] = None
        df["parsed_material"] = [None] * 6 + ["two-tone"] * 2
        df = assign_material(df)
        df["clean"] = True
        assert dominant_material(df)["Datejust"] == "steel"

    def test_dominant_weekly_filters_to_stratum(self):
        dom = dominant_weekly(self._weekly(), {"Datejust": "steel"})
        assert set(dom["material"]) == {"steel"}
        assert len(dom) == 3

    def test_index_chains_within_strata(self):
        # Two strata, both flat — a changing mix must NOT move the index
        weekly = self._weekly()
        index = build_market_index(weekly)
        assert index.max() == pytest.approx(100.0)
        assert index.min() == pytest.approx(100.0)
