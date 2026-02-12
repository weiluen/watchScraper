import pytest
from pydantic import ValidationError

from watchscraper.schemas import ScrapedListing


class TestScrapedListing:
    def test_valid_listing(self):
        listing = ScrapedListing(
            source_name="ebay",
            external_id="12345",
            title="Rolex Submariner 126610LN",
            price_usd=1500000,
            price_type="sold",
        )
        assert listing.price_usd == 1500000
        assert listing.price_type == "sold"
        assert listing.condition == "unknown"

    def test_negative_price_rejected(self):
        with pytest.raises(ValidationError):
            ScrapedListing(
                source_name="ebay",
                external_id="12345",
                title="Test",
                price_usd=-100,
                price_type="sold",
            )

    def test_zero_price_rejected(self):
        with pytest.raises(ValidationError):
            ScrapedListing(
                source_name="ebay",
                external_id="12345",
                title="Test",
                price_usd=0,
                price_type="sold",
            )

    def test_invalid_price_type_rejected(self):
        with pytest.raises(ValidationError):
            ScrapedListing(
                source_name="ebay",
                external_id="12345",
                title="Test",
                price_usd=1000,
                price_type="invalid",
            )

    def test_optional_fields(self):
        listing = ScrapedListing(
            source_name="chrono24",
            external_id="abc",
            title="AP Royal Oak",
            price_usd=5000000,
            price_type="asking",
            has_box=True,
            has_papers=False,
            listing_url="https://example.com/123",
            reference_parsed="15500ST",
        )
        assert listing.has_box is True
        assert listing.has_papers is False
        assert listing.reference_parsed == "15500ST"
