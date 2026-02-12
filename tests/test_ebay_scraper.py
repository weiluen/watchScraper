from watchscraper.scrapers.ebay import EbayScraper


class TestEbayParser:
    """Test eBay HTML parsing with synthetic HTML fragments."""

    def setup_method(self):
        self.scraper = EbayScraper()

    def test_extract_item_id_valid(self):
        url = "https://www.ebay.com/itm/123456789?hash=item..."
        assert EbayScraper._extract_item_id(url) == "123456789"

    def test_extract_item_id_no_match(self):
        assert EbayScraper._extract_item_id("https://www.ebay.com/sch/") is None

    def test_parse_price_usd(self):
        assert EbayScraper._parse_price("$15,500.00") == 1550000

    def test_parse_price_no_symbol(self):
        assert EbayScraper._parse_price("12,000.00") == 1200000

    def test_parse_price_too_low(self):
        assert EbayScraper._parse_price("$50.00") is None

    def test_parse_price_invalid(self):
        assert EbayScraper._parse_price("N/A") is None

    def test_normalize_condition_new(self):
        assert EbayScraper._normalize_condition("Brand New") == "new"

    def test_normalize_condition_preowned(self):
        assert EbayScraper._normalize_condition("Pre-Owned") == "good"

    def test_normalize_condition_unknown(self):
        assert EbayScraper._normalize_condition("Other") == "unknown"

    def test_try_extract_ref_rolex(self):
        assert EbayScraper._try_extract_ref("Rolex Submariner 126610LN Box Papers") == "126610LN"

    def test_try_extract_ref_patek(self):
        assert EbayScraper._try_extract_ref("Patek Philippe Nautilus 5711/1A Blue") == "5711/1A"

    def test_try_extract_ref_ap(self):
        assert EbayScraper._try_extract_ref("AP Royal Oak 15500ST Blue Dial") == "15500ST"

    def test_try_extract_ref_no_match(self):
        assert EbayScraper._try_extract_ref("Nice watch for sale") is None

    def test_parse_results_legacy_html(self):
        html = """
        <html><body>
        <div class="s-item__wrapper">
            <div class="s-item__title"><span role="heading">Rolex Submariner 126610LN 2024 Box Papers</span></div>
            <a class="s-item__link" href="https://www.ebay.com/itm/334455667788?hash=xyz">Link</a>
            <span class="s-item__price">$15,500.00</span>
            <span class="SECONDARY_INFO">Pre-Owned</span>
        </div>
        <div class="s-item__wrapper">
            <div class="s-item__title"><span role="heading">Shop on eBay</span></div>
            <a class="s-item__link" href="https://www.ebay.com/sch/">Link</a>
            <span class="s-item__price">$0.99</span>
        </div>
        </body></html>
        """
        results = self.scraper._parse_results(html)
        assert len(results) == 1
        assert results[0].external_id == "334455667788"
        assert results[0].price_usd == 1550000
        assert results[0].price_type == "sold"
        assert results[0].reference_parsed == "126610LN"
        assert results[0].condition == "good"

    def test_parse_results_new_s_card_html(self):
        html = """
        <html><body>
        <ul class="srp-results">
            <li class="s-card s-card--horizontal">
                <span>Sold  Feb 8, 2026</span>
                <a class="s-card__title" href="https://www.ebay.com/itm/445566778899?hash=abc">
                    Rolex GMT-Master II 126710BLNR Batman 2024 Full Set
                </a>
                <span>Pre-Owned</span>
                <span class="su-styled-text s-card__price">$18,250.00</span>
            </li>
            <li class="srp-river-answer">
                <span>Have one to sell?</span>
            </li>
        </ul>
        </body></html>
        """
        results = self.scraper._parse_results(html)
        assert len(results) == 1
        assert results[0].external_id == "445566778899"
        assert results[0].price_usd == 1825000
        assert results[0].price_type == "sold"
        assert results[0].reference_parsed == "126710BLNR"
        assert results[0].condition == "good"
