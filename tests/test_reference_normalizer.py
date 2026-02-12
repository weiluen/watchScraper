from watchscraper.normalizers.reference import normalize_reference, resolve_alias


class TestNormalizeReference:
    def test_rolex_with_prefix(self):
        assert normalize_reference("Ref. 126710BLNR", "rolex") == "126710BLNR"

    def test_rolex_with_spaces(self):
        assert normalize_reference("126610 LN", "rolex") == "126610LN"

    def test_rolex_plain(self):
        assert normalize_reference("116500LN", "rolex") == "116500LN"

    def test_patek_with_variant(self):
        assert normalize_reference("5711/1A-010", "patek-philippe") == "5711/1A"

    def test_patek_plain(self):
        assert normalize_reference("5167A", "patek-philippe") == "5167A"

    def test_ap_with_full_ref(self):
        assert normalize_reference("15500ST.OO.1220ST.01", "audemars-piguet") == "15500ST"

    def test_ap_plain(self):
        assert normalize_reference("15202ST", "audemars-piguet") == "15202ST"

    def test_generic_detection(self):
        assert normalize_reference("126610LV") == "126610LV"

    def test_uppercasing(self):
        assert normalize_reference("126610ln", "rolex") == "126610LN"


class TestResolveAlias:
    def test_known_alias_batman(self):
        assert resolve_alias("Batman") == "126710BLNR"

    def test_known_alias_pepsi(self):
        assert resolve_alias("Pepsi") == "126710BLRO"

    def test_known_alias_starbucks(self):
        assert resolve_alias("Starbucks") == "126610LV"

    def test_direct_canonical(self):
        assert resolve_alias("126710BLNR") == "126710BLNR"

    def test_unknown_returns_none(self):
        assert resolve_alias("UNKNOWN_REF_999") is None
