import pytest

from watchscraper.matching import CatalogEntry, Matcher, extract_attributes


def entry(**kw) -> CatalogEntry:
    base = dict(
        watch_id=1, brand_slug="rolex", ref="126610LN", family="Submariner",
        start=2020, end=None, dial="black", material_class="steel",
        size_mm=41.0, bezel="black", bracelet="oyster", has_date=True,
    )
    return CatalogEntry(**{**base, **kw})


@pytest.fixture
def matcher() -> Matcher:
    entries = [
        # Submariner generations
        entry(watch_id=1, ref="126610LN", start=2020, end=None, size_mm=41),
        entry(watch_id=2, ref="116610LN", start=2010, end=2020, size_mm=40),
        entry(watch_id=3, ref="16610", start=1988, end=2010, size_mm=40),
        entry(watch_id=4, ref="116610LV", start=2010, end=2020, size_mm=40,
              bezel="green", dial="green"),
        entry(watch_id=5, ref="126610LV", start=2020, end=None, size_mm=41,
              bezel="green", dial="black"),
        entry(watch_id=6, ref="16610LV", start=2003, end=2010, size_mm=40,
              bezel="green", dial="black"),
        entry(watch_id=7, ref="114060", start=2012, end=2020, size_mm=40,
              has_date=False),
        # GMT generations
        entry(watch_id=10, ref="126710BLNR", family="GMT-Master II",
              start=2019, end=None, size_mm=40, bezel="blue/black",
              bracelet="jubilee/oyster"),
        entry(watch_id=11, ref="116710BLNR", family="GMT-Master II",
              start=2013, end=2019, size_mm=40, bezel="blue/black",
              bracelet="oyster"),
        entry(watch_id=12, ref="126710BLRO", family="GMT-Master II",
              start=2018, end=None, size_mm=40, bezel="red/blue",
              bracelet="jubilee/oyster"),
        entry(watch_id=13, ref="16710", family="GMT-Master II",
              start=1989, end=2007, size_mm=40, bezel=None,
              bracelet="oyster/jubilee"),
        # Daytona panda
        entry(watch_id=20, ref="116500LN", family="Daytona", start=2016,
              end=2023, size_mm=40, dial="white", has_date=False),
        entry(watch_id=21, ref="126500LN", family="Daytona", start=2023,
              end=None, size_mm=40, dial="white", has_date=False),
        # Omega Snoopy
        entry(watch_id=30, brand_slug="omega", ref="310.32.42.50.02.001",
              family="Speedmaster", start=2020, end=None, size_mm=42,
              dial="silver", has_date=False),
        # Patek
        entry(watch_id=40, brand_slug="patek-philippe", ref="5711/1A",
              family="Nautilus", start=2006, end=2021, size_mm=40,
              dial="blue", bezel=None, bracelet="integrated"),
    ]
    aliases = {"5711/1A-010": 40, "126610 LN": 1}
    nicknames = {
        "Hulk": [4],
        "Starbucks": [5],
        "Kermit": [6],
        "Batman": [10, 11],
        "Pepsi": [12, 13],
        "Panda": [20, 21],
        "Snoopy": [30],
    }
    return Matcher(entries, aliases, nicknames)


class TestExtractAttributes:
    def test_year(self):
        assert extract_attributes("Rolex Submariner 2021 full set")["year"] == 2021

    def test_latest_year_wins(self):
        attrs = extract_attributes("Vintage style 1990s — 2019 card")
        assert attrs["year"] == 2019

    def test_year_not_from_reference_digits(self):
        # 16610 and 126610LN contain no standalone 4-digit year
        assert "year" not in extract_attributes("Rolex Submariner 16610 black")

    def test_size(self):
        assert extract_attributes("Submariner 41mm unworn")["size_mm"] == 41.0

    def test_dial_and_bezel(self):
        attrs = extract_attributes("black dial green bezel Submariner")
        assert attrs["dial"] == "black"
        assert attrs["bezel"] == "green"

    def test_panda_dial_is_white(self):
        assert extract_attributes("Daytona panda dial")["dial"] == "white"

    def test_two_tone(self):
        assert extract_attributes("Submariner two-tone 16613")["material"] == "two-tone"
        assert extract_attributes("Datejust Steel & Gold")["material"] == "two-tone"

    def test_no_date(self):
        assert extract_attributes("Submariner no date 114060")["no_date"] is True

    def test_bracelet(self):
        assert extract_attributes("GMT on jubilee bracelet")["bracelet"] == "jubilee"


class TestExactRef:
    def test_exact_ref_high_confidence(self, matcher):
        r = matcher.match("Rolex Submariner Date 126610LN 2022 box papers")
        assert r.watch_id == 1
        assert r.method == "exact_ref"
        assert r.confidence == 0.95

    def test_year_conflict_downgrades_but_ref_wins(self, matcher):
        # A "2023" listing of a ref that ended in 2010
        r = matcher.match("2023 Rolex Submariner 16610 serviced")
        assert r.watch_id == 3
        assert r.method == "exact_ref"
        assert r.confidence == 0.80
        assert r.attributes.get("year_conflict") is True

    def test_year_within_tolerance_no_conflict(self, matcher):
        # 2021 vs end=2020 — transition-year stock, no conflict
        r = matcher.match("Rolex Submariner 116610LN 2021")
        assert r.confidence == 0.95

    def test_alias_resolution(self, matcher):
        r = matcher.match("Patek Philippe Nautilus 5711/1A-010 blue")
        assert r.watch_id == 40
        assert r.method in ("exact_ref", "alias")


class TestNickname:
    def test_unique_nickname(self, matcher):
        r = matcher.match("Rolex Submariner Hulk full set 2016")
        assert r.watch_id == 4
        assert r.method == "nickname"
        assert r.confidence == 0.80

    def test_hulk_vs_starbucks_are_different_watches(self, matcher):
        hulk = matcher.match("Rolex Submariner Hulk")
        starbucks = matcher.match("Rolex Submariner Starbucks")
        assert hulk.watch_id == 4
        assert starbucks.watch_id == 5

    def test_batman_year_picks_generation(self, matcher):
        old = matcher.match("Rolex GMT Batman 2015")
        new = matcher.match("Rolex GMT Batman 2022")
        assert old.watch_id == 11
        assert new.watch_id == 10
        assert old.confidence == 0.80

    def test_batman_jubilee_hint(self, matcher):
        r = matcher.match("Rolex GMT-Master II Batman jubilee bracelet")
        assert r.watch_id == 10
        assert r.confidence == 0.75

    def test_batman_no_hints_defaults_to_current_gen(self, matcher):
        r = matcher.match("Rolex GMT Batman")
        assert r.watch_id == 10
        assert r.method == "nickname_default_gen"
        assert r.confidence == 0.55

    def test_pepsi_vintage_vs_modern(self, matcher):
        vintage = matcher.match("Rolex GMT Master II Pepsi 1995")
        modern = matcher.match("Rolex GMT Master II Pepsi 2021")
        assert vintage.watch_id == 13
        assert modern.watch_id == 12

    def test_panda_generation_by_year(self, matcher):
        old = matcher.match("Rolex Daytona Panda 2019")
        new = matcher.match("Rolex Daytona Panda 2024")
        assert old.watch_id == 20
        assert new.watch_id == 21

    def test_snoopy(self, matcher):
        r = matcher.match("Omega Speedmaster Snoopy 50th Anniversary")
        assert r.watch_id == 30


class TestAttributeNarrowing:
    def test_no_date_plus_year(self, matcher):
        r = matcher.match("Rolex Submariner No Date 2015", query="Rolex Submariner")
        assert r.watch_id == 7
        assert r.method == "attributes"

    def test_size_narrows_generation(self, matcher):
        # 41mm + green bezel + black dial → 126610LV; 4 (green dial) excluded
        r = matcher.match(
            "Rolex Submariner 41mm black dial green bezel", query="Rolex Submariner"
        )
        assert r.watch_id == 5

    def test_ambiguous_stays_family_only(self, matcher):
        r = matcher.match("Rolex Submariner nice watch", query="Rolex Submariner")
        assert r.watch_id is None
        assert r.method == "family"
        assert r.family == "Submariner"
        assert r.confidence == 0.3

    def test_unknown_stays_none(self, matcher):
        r = matcher.match("Seiko 5 automatic")
        assert r.watch_id is None
        assert r.method == "none"


class TestFamilyPropagation:
    def test_ref_match_carries_catalog_family(self, matcher):
        r = matcher.match("Rolex 126710BLRO unpolished")
        assert r.family == "GMT-Master II"


class TestNicknameSafety:
    """Regression tests for real mismatches found in scraped data."""

    def test_nickname_never_crosses_brands(self, matcher):
        # "panda dial" on an Omega must not match the Rolex Daytona Panda
        r = matcher.match("Omega Speedmaster panda dial chronograph")
        assert r.watch_id != 20 and r.watch_id != 21

    def test_year_outside_all_windows_refuses_match(self, matcher):
        # A 1969 Pepsi predates every cataloged Pepsi generation (1989+ here);
        # matching any of them would misprice a vintage watch
        r = matcher.match("1969 Rolex GMT-Master Pepsi amazing patina")
        assert r.watch_id is None
        assert r.family == "GMT-Master II"

    def test_vintage_four_digit_ref_extraction(self, matcher):
        from watchscraper.matching import extract_ref_candidates

        candidates = extract_ref_candidates("Rolex GMT Master 1675 Pepsi MK5")
        assert "1675" in candidates
