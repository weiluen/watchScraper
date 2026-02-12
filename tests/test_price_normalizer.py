import pytest

from watchscraper.normalizers.price import convert_to_usd_cents, detect_currency


class TestConvertToUsdCents:
    def test_usd(self):
        assert convert_to_usd_cents(10000.0, "USD") == 1000000

    def test_eur(self):
        result = convert_to_usd_cents(10000.0, "EUR")
        assert result == 1080000  # 10000 * 1.08 * 100

    def test_gbp(self):
        result = convert_to_usd_cents(10000.0, "GBP")
        assert result == 1270000  # 10000 * 1.27 * 100

    def test_unknown_currency_treated_as_usd(self):
        result = convert_to_usd_cents(1000.0, "XYZ")
        assert result == 100000


class TestDetectCurrency:
    def test_dollar_sign(self):
        amount, code = detect_currency("$15,000")
        assert amount == 15000.0
        assert code == "USD"

    def test_euro_sign(self):
        amount, code = detect_currency("€12,500")
        assert amount == 12500.0
        assert code == "EUR"

    def test_pound_sign(self):
        amount, code = detect_currency("£8,000")
        assert amount == 8000.0
        assert code == "GBP"

    def test_plain_number(self):
        amount, code = detect_currency("25000")
        assert amount == 25000.0
        assert code == "USD"

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            detect_currency("not a price")
