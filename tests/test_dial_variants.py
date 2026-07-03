import pytest

from watchscraper.analysis import flag_junk
from watchscraper.matching import CatalogEntry, Matcher
from tests.test_analysis import make_df


def entry(**kw) -> CatalogEntry:
    base = dict(
        watch_id=1, brand_slug="rolex", ref="116508", family="Daytona",
        start=2016, end=2023, dial=None, material_class="yellow-gold",
        size_mm=40.0, bezel=None, bracelet="oyster", has_date=False,
        dial_variant=None,
    )
    return CatalogEntry(**{**base, **kw})


@pytest.fixture
def matcher() -> Matcher:
    entries = [
        entry(watch_id=1),  # 116508 parent (mixed bucket)
        entry(watch_id=2, dial_variant="Green", dial="green"),
        entry(watch_id=3, dial_variant="Champagne", dial="champagne"),
        entry(watch_id=4, dial_variant="Black", dial="black"),
        # Patek 5711/1A parent + variants
        entry(watch_id=10, brand_slug="patek-philippe", ref="5711/1A",
              family="Nautilus", start=2006, end=2021, size_mm=40,
              material_class="steel"),
        entry(watch_id=11, brand_slug="patek-philippe", ref="5711/1A",
              family="Nautilus", start=2006, end=2021, size_mm=40,
              material_class="steel", dial_variant="Blue", dial="blue"),
        entry(watch_id=12, brand_slug="patek-philippe", ref="5711/1A",
              family="Nautilus", start=2006, end=2021, size_mm=40,
              material_class="steel", dial_variant="Green", dial="green"),
    ]
    aliases = {"5711/1A-010": 11, "5711/1A-014": 12}
    nicknames = {"John Mayer": [2]}
    dial_terms = {
        ("rolex", "116508", "green"): "Green",
        ("rolex", "116508", "champagne"): "Champagne",
        ("rolex", "116508", "gold"): "Champagne",
        ("rolex", "116508", "black"): "Black",
        ("patek-philippe", "5711/1A", "blue"): "Blue",
        ("patek-philippe", "5711/1A", "green"): "Green",
    }
    return Matcher(entries, aliases, nicknames, dial_terms=dial_terms)


class TestVariantResolution:
    def test_dial_term_picks_variant(self, matcher):
        r = matcher.match("Rolex Daytona 116508 Green Dial 18K Yellow Gold")
        assert r.watch_id == 2
        assert r.confidence == 0.92

    def test_champagne_via_gold_synonym(self, matcher):
        r = matcher.match("Rolex Daytona 116508 Gold Dial Oyster")
        assert r.watch_id == 3

    def test_nickname_in_title_is_decisive(self, matcher):
        r = matcher.match("Rolex Daytona 116508 John Mayer 18ct Yellow Gold")
        assert r.watch_id == 2
        assert r.confidence == 0.95

    def test_unknown_dial_parks_on_parent(self, matcher):
        r = matcher.match("Rolex Cosmograph Daytona 116508 Oyster Bracelet")
        assert r.watch_id == 1  # the mixed parent bucket
        assert r.confidence == 0.85
        assert r.attributes.get("dial_unresolved") is True

    def test_nickname_without_ref_still_finds_variant(self, matcher):
        r = matcher.match("Rolex Daytona John Mayer full set")
        assert r.watch_id == 2
        assert r.method == "nickname"

    def test_patek_dash_suffix_pins_variant(self, matcher):
        green = matcher.match("Patek Philippe Nautilus 5711/1A-014")
        blue = matcher.match("Patek Philippe Nautilus 5711/1A-010")
        assert green.watch_id == 12
        assert blue.watch_id == 11

    def test_patek_bare_ref_with_dial_term(self, matcher):
        r = matcher.match("Patek Philippe Nautilus 5711/1A green dial")
        assert r.watch_id == 12

    def test_patek_bare_ref_unknown_dial_is_parent(self, matcher):
        r = matcher.match("Patek Philippe Nautilus 5711/1A full set")
        assert r.watch_id == 10


class TestAftermarketDialJunk:
    @pytest.mark.parametrize(
        "title",
        [
            "Rolex Cosmograph Daytona 116508 Custom Green Dial 18K Yellow Gold",
            "Rolex Daytona 116508 aftermarket diamond dial",
            "Rolex Datejust redial vintage",
            "Rolex Day-Date iced out custom",
            "Rolex Submariner diamond set bezel 16610",
        ],
    )
    def test_aftermarket_mods_are_junk(self, title):
        df = flag_junk(make_df([{"title": title}]))
        assert bool(df["is_junk"].iloc[0]), title

    @pytest.mark.parametrize(
        "title",
        [
            "Rolex Daytona 116508 John Mayer Green Dial 18ct Yellow Gold",
            "Rolex Daytona 116508 Factory Diamond Dial",  # factory-set is genuine
            "Patek Philippe Nautilus 5711/1A-014 green dial",
        ],
    )
    def test_genuine_variants_survive(self, title):
        df = flag_junk(make_df([{"title": title}]))
        assert not bool(df["is_junk"].iloc[0]), title
