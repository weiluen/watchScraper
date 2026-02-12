import logging
import re
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from watchscraper.schemas import ScrapedListing
from watchscraper.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class HodinkeeScraper(BaseScraper):
    """Scrape Hodinkee / Crown & Caliber asking prices.

    Hodinkee Shop and Crown & Caliber are curated pre-owned dealers with
    well-structured listing pages.
    """

    source_name = "hodinkee"
    BASE_URL = "https://shop.hodinkee.com"

    def scrape(self, query: str, max_pages: int = 3, **kwargs) -> list[ScrapedListing]:
        listings: list[ScrapedListing] = []

        for page in range(1, max_pages + 1):
            url = (
                f"{self.BASE_URL}/collections/all"
                f"?q={quote_plus(query)}&page={page}"
            )
            logger.info("Hodinkee page %d: %s", page, url)

            try:
                resp = self._get(url)
            except Exception:
                logger.exception("Failed to fetch Hodinkee page %d", page)
                break

            page_listings = self._parse_results(resp.text)
            if not page_listings:
                break
            listings.extend(page_listings)
            logger.info(
                "Parsed %d listings from Hodinkee page %d", len(page_listings), page
            )

        logger.info("Hodinkee total: %d listings for '%s'", len(listings), query)
        return listings

    def _parse_results(self, html: str) -> list[ScrapedListing]:
        soup = BeautifulSoup(html, "lxml")
        results: list[ScrapedListing] = []

        # Product cards — Hodinkee uses grid items with product-card class
        cards = soup.select(
            "div.product-card, div.collection-product, article.product"
        )
        if not cards:
            # Fallback: try JSON-LD structured data
            results = self._parse_json_ld(soup)
            if results:
                return results
            # Fallback: try generic product links
            cards = soup.select("a[href*='/products/']")

        for card in cards:
            try:
                listing = self._parse_card(card)
                if listing:
                    results.append(listing)
            except Exception:
                logger.debug("Skipping Hodinkee card", exc_info=True)

        return results

    def _parse_card(self, card) -> ScrapedListing | None:
        # Title
        title_el = card.select_one(
            "h3, h2, .product-card__title, .product-title, span.title"
        )
        if title_el:
            title = title_el.get_text(strip=True)
        elif card.name == "a":
            title = card.get_text(strip=True)
        else:
            return None

        if not title or len(title) < 5:
            return None

        # URL
        link_el = card if card.name == "a" else card.select_one("a[href]")
        url = ""
        if link_el:
            href = link_el.get("href", "")
            url = href if href.startswith("http") else f"{self.BASE_URL}{href}"

        # External ID from URL
        external_id = ""
        if url:
            # /products/rolex-submariner-... → rolex-submariner-...
            parts = url.rstrip("/").split("/")
            external_id = parts[-1] if parts else ""
        if not external_id:
            return None

        # Price
        price_el = card.select_one(
            "span.price, span.product-price, .product-card__price, .money"
        )
        if not price_el:
            return None
        price_cents = self._parse_price(price_el.get_text(strip=True))
        if not price_cents:
            return None

        return ScrapedListing(
            source_name=self.source_name,
            external_id=f"hodinkee-{external_id}",
            title=title,
            price_usd=price_cents,
            price_type="asking",
            listing_url=url,
            reference_parsed=self._try_extract_ref(title),
            raw_data={"title": title, "url": url},
        )

    def _parse_json_ld(self, soup: BeautifulSoup) -> list[ScrapedListing]:
        """Parse JSON-LD product structured data as fallback."""
        import json

        results: list[ScrapedListing] = []
        for script in soup.select('script[type="application/ld+json"]'):
            try:
                data = json.loads(script.string or "")
                if isinstance(data, list):
                    for item in data:
                        listing = self._from_json_ld(item)
                        if listing:
                            results.append(listing)
                else:
                    listing = self._from_json_ld(data)
                    if listing:
                        results.append(listing)
            except (json.JSONDecodeError, Exception):
                continue
        return results

    def _from_json_ld(self, data: dict) -> ScrapedListing | None:
        if data.get("@type") != "Product":
            return None
        title = data.get("name", "")
        offers = data.get("offers", {})
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        price = offers.get("price")
        if not price:
            return None
        try:
            price_cents = int(float(price) * 100)
        except (ValueError, TypeError):
            return None
        if price_cents <= 0:
            return None

        url = data.get("url", offers.get("url", ""))
        sku = data.get("sku", "")
        external_id = f"hodinkee-{sku}" if sku else f"hodinkee-{title[:50]}"

        return ScrapedListing(
            source_name=self.source_name,
            external_id=external_id,
            title=title,
            price_usd=price_cents,
            price_type="asking",
            listing_url=url,
            reference_parsed=self._try_extract_ref(title),
            raw_data=data,
        )

    @staticmethod
    def _parse_price(text: str) -> int | None:
        text = text.replace(",", "").strip()
        m = re.search(r"\$?([\d]+\.?\d*)", text)
        if not m:
            return None
        dollars = float(m.group(1))
        if dollars < 100:
            return None
        return int(dollars * 100)

    @staticmethod
    def _try_extract_ref(title: str) -> str | None:
        patterns = [
            r"\b(1[12]\d{4}[A-Z]{0,6})\b",
            r"\b(5\d{3}[A-Z]?/\d[A-Z]+)\b",
            r"\b(1[56]\d{3}[A-Z]{2})\b",
            r"\b(26\d{3}[A-Z]{2})\b",
        ]
        for pat in patterns:
            m = re.search(pat, title)
            if m:
                return m.group(1)
        return None
