"""Smoke tests for the market-research services against the live snapshot.

These are integration-style: they build the real MarketSnapshot from the DB
and assert the research views are well-formed. They exercise the query logic
end to end, which is where research bugs live.
"""

import pytest

from watchscraper.web.services import (
    appraise,
    brand_detail_payload,
    brands_payload,
    get_market,
)
from watchscraper.web import research as R


@pytest.fixture(scope="module")
def snap():
    return get_market()


class TestIndexes:
    def test_shape(self, snap):
        ix = R.indexes_payload(snap)
        assert ix["overall"] is not None
        assert ix["overall"]["level"] is not None
        assert isinstance(ix["brands"], list) and len(ix["brands"]) >= 1
        # every index rebases to 100 at its start
        for cat in ("brands", "groups", "price_ranges"):
            for i in ix[cat]:
                if i["points"]:
                    assert abs(i["points"][0]["value"] - 100.0) < 1e-6

    def test_detail_lookup(self, snap):
        d = R.index_detail(snap, "overall")
        assert d and d["slug"] == "overall"
        assert R.index_detail(snap, "nonexistent-index") is None


class TestScreener:
    def test_min_price_filters(self, snap):
        cheap = R.top_performers(snap, min_price=0)
        pricey = R.top_performers(snap, min_price=20000)
        assert len(pricey) <= len(cheap)
        assert all(r["median_usd"] >= 20000 for r in pricey)

    def test_sort_desc(self, snap):
        rows = R.top_performers(snap, sort="price_desc", limit=10)
        vals = [r["median_usd"] or 0 for r in rows]
        assert vals == sorted(vals, reverse=True)


class TestValueRetention:
    def test_brand_leaderboard(self, snap):
        board = R.value_retention_leaderboard(snap)
        assert len(board) >= 1
        # sorted descending by retention
        rets = [b["retention_pct"] for b in board if b["retention_pct"] is not None]
        assert rets == sorted(rets, reverse=True)
        # each brand has best/worst lists
        assert all("best" in b and "worst" in b for b in board)


class TestForecasts:
    def test_gated_masks_values(self, snap):
        gated = R.forecast_leaderboard(snap, gated=True)
        assert all(f["forecast_pct"] is None and f["forecast_masked"] for f in gated)
        ungated = R.forecast_leaderboard(snap, gated=False)
        assert any(f["forecast_pct"] is not None for f in ungated)


class TestLists:
    def test_all_four_lists_run(self, snap):
        for slug in ("above-retail", "steady-gainers", "comebacks", "resilient-sports"):
            d = R.collecting_list(snap, slug)
            assert d is not None
            assert d["slug"] == slug
            assert isinstance(d["results"], list)

    def test_above_retail_only_positive_premium(self, snap):
        d = R.collecting_list(snap, "above-retail")
        assert all(r["premium_pct"] > 0 for r in d["results"] if r["premium_pct"] is not None)

    def test_unknown_list_none(self, snap):
        assert R.collecting_list(snap, "no-such-list") is None


class TestSearch:
    def test_finds_by_nickname(self, snap):
        r = R.search(snap, "hulk")
        assert any("116610lv" in w["slug"] for w in r["watches"])

    def test_short_query_empty(self, snap):
        assert R.search(snap, "a")["watches"] == []


class TestAppraise:
    def test_multipliers_applied(self, snap):
        refs = R.refs_payload(snap) if hasattr(R, "refs_payload") else None
        # pick a known priced ref
        a = appraise(snap, "rolex-116508-green", "new", "watch_only")
        assert a is not None
        # new (+) and watch-only (−) move opposite directions from base
        assert a["condition_mult"] > 1.0
        assert a["contents_mult"] < 1.0
        # estimate = base × condition × completeness (within rounding)
        assert a["estimate"] == pytest.approx(
            a["base_value"] * a["condition_mult"] * a["contents_mult"], rel=0.001
        )

    def test_unknown_ref(self, snap):
        assert appraise(snap, "not-a-real-slug", "good", "full_set") is None


class TestBrands:
    def test_brands_and_detail(self, snap):
        bs = brands_payload(snap)
        assert len(bs) >= 5
        rolex = brand_detail_payload(snap, "rolex")
        assert rolex and rolex["brand"] == "Rolex"
        assert rolex["n_refs"] >= 1 and len(rolex["collections"]) >= 1
