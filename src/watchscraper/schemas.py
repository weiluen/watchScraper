from datetime import datetime

from pydantic import BaseModel, field_validator, model_validator


class ScrapedListing(BaseModel):
    """Validated listing coming out of a scraper, before DB insertion.

    Every listing carries its parsed variant attributes (year, size,
    material, dial, bezel, bracelet, date/no-date) extracted from the title
    at scrape time — the matching engine and analysis layers consume them
    without re-parsing.
    """

    source_name: str
    external_id: str
    title: str
    price_usd: int  # in cents
    price_type: str  # asking | sold | estimated
    condition: str = "unknown"
    has_box: bool | None = None
    has_papers: bool | None = None
    listing_url: str | None = None
    reference_parsed: str | None = None
    parsed_year: int | None = None
    parsed_attributes: dict | None = None
    observed_at: datetime | None = None
    raw_data: dict | None = None

    @model_validator(mode="after")
    def extract_variant_attributes(self) -> "ScrapedListing":
        if self.parsed_attributes is None and self.title:
            from watchscraper.matching import extract_attributes

            attrs = extract_attributes(self.title)
            self.parsed_attributes = attrs or None
            if self.parsed_year is None:
                self.parsed_year = attrs.get("year")
        return self

    @field_validator("price_usd")
    @classmethod
    def price_must_be_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("price_usd must be positive")
        return v

    @field_validator("price_type")
    @classmethod
    def valid_price_type(cls, v: str) -> str:
        allowed = {"asking", "sold", "estimated"}
        if v not in allowed:
            raise ValueError(f"price_type must be one of {allowed}")
        return v
