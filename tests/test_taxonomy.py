import numpy as np
import pandas as pd
import pytest

from watchscraper.taxonomy import (
    AtomKey,
    analyze_reference_granularity,
    reconcile_with_catalog,
)
from watchscraper.valuation import _size_band


class TestSizeBand:
    @pytest.mark.parametrize("mm,band", [
        (28, "sub34"), (31, "sub34"), (36, "34-37"), (40, "38-41"),
        (41, "38-41"), (42, "42+"), (44, "42+"), (None, None),
    ])
    def test_bands(self, mm, band):
        assert _size_band(mm) == band


class TestAtomKey:
    def test_variant_label(self):
        k = AtomKey(brand="Rolex", reference="116508", dial="Green", family="Daytona")
        assert "116508" in k.label() and "Green" in k.label()

    def test_family_generic_label(self):
        k = AtomKey(brand="Rolex", reference=None, material="two-tone", family="Datejust")
        assert "Datejust" in k.label() and "two-tone" in k.label()


def _sold(rows):
    df = pd.DataFrame(rows)
    df["match_confidence"] = 0.95
    df["parsed_attributes"] = [{} for _ in range(len(df))]
    return df


class TestGranularityAnalysis:
    def test_splits_when_dense_and_divergent(self):
        # Green trades ~60% above champagne, both dense → recommend split
        rows = (
            [{"linked_brand": "Rolex", "linked_ref": "116508", "linked_dial": "Green",
              "price": 70000.0} for _ in range(8)]
            + [{"linked_brand": "Rolex", "linked_ref": "116508", "linked_dial": "Champagne",
                "price": 43000.0} for _ in range(8)]
        )
        findings = analyze_reference_granularity(_sold(rows), min_per_group=5)
        assert len(findings) == 1
        assert findings[0].recommend_split is True

    def test_no_split_when_gap_small(self):
        # Two dials trade within a few percent → one market, dial is hedonic
        rows = (
            [{"linked_brand": "Rolex", "linked_ref": "126610LN", "linked_dial": "Black",
              "price": 15000.0 + i} for i in range(8)]
            + [{"linked_brand": "Rolex", "linked_ref": "126610LN", "linked_dial": "Blue",
                "price": 15300.0 + i} for i in range(8)]
        )
        findings = analyze_reference_granularity(_sold(rows), min_per_group=5)
        assert findings and findings[0].recommend_split is False

    def test_no_finding_when_thin(self):
        # Only 3 sales of one dial → below density floor, no finding
        rows = [{"linked_brand": "Rolex", "linked_ref": "116508", "linked_dial": "Green",
                 "price": 70000.0} for _ in range(3)]
        findings = analyze_reference_granularity(_sold(rows), min_per_group=5)
        assert findings == []

    def test_reconcile_flags_missed_and_thin(self):
        rows = (
            [{"linked_brand": "Rolex", "linked_ref": "116509", "linked_dial": "Blue",
              "price": 40000.0} for _ in range(6)]
            + [{"linked_brand": "Rolex", "linked_ref": "116509", "linked_dial": "Silver",
                "price": 60000.0} for _ in range(6)]
        )
        findings = analyze_reference_granularity(_sold(rows), min_per_group=5)
        rec = reconcile_with_catalog(findings, catalog_variant_refs={"116508"})
        # 116509 splits in data but isn't in the catalog → missed
        assert "116509" in rec["missed_by_catalog"]
        # 116508 is curated but had no data here → thin
        assert "116508" in rec["curated_but_thin"]
