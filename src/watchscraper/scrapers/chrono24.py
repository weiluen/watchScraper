import logging
import re
import time
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from watchscraper.schemas import ScrapedListing
from watchscraper.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class Chrono24Scraper(BaseScraper):
    """Scrape Chrono24 asking prices.

    Uses curl_cffi with Chrome TLS impersonation to bypass Cloudflare.
    Cloudflare blocks page 2+, so we get ~60 listings per query.
    """

    source_name = "chrono24"

    SEARCH_URL = (
        "https://www.chrono24.com/search/index.htm"
        "?query={query}&dosearch=true"
    )

    def scrape(self, query: str, max_pages: int = 1, **kwargs) -> list[ScrapedListing]:
        listings = self._scrape_curl_cffi(query)
        if listings:
            return listings

        # Fallback: try the chrono24 PyPI package
        logger.info("curl_cffi returned no results, trying chrono24 package")
        return self._scrape_via_package(query)

    def _scrape_curl_cffi(self, query: str) -> list[ScrapedListing]:
        try:
            from curl_cffi import requests as cffi_requests
        except ImportError:
            logger.warning("curl_cffi not installed — pip install curl_cffi")
            return []

        url = self.SEARCH_URL.format(query=quote_plus(query))
        logger.info("Chrono24 curl_cffi: %s", url)

        try:
            resp = cffi_requests.get(url, impersonate="chrome", timeout=20)
        except Exception:
            logger.exception("Chrono24 curl_cffi request failed")
            return []

        if resp.status_code != 200:
            logger.warning("Chrono24 returned status %d", resp.status_code)
            return []

        listings = self._parse_results(resp.text)
        logger.info("Chrono24: %d listings for '%s'", len(listings), query)
        return listings

    def _parse_results(self, html: str) -> list[ScrapedListing]:
        soup = BeautifulSoup(html, "lxml")
        cards = soup.select("div.js-listing-item-container")
        if not cards:
            # Legacy layout fallback
            cards = soup.select("div.article-item-container")

        results: list[ScrapedListing] = []
        seen_ids: set[str] = set()
        for card in cards:
            try:
                listing = self._parse_card(card)
                if listing and listing.external_id not in seen_ids:
                    seen_ids.add(listing.external_id)
                    results.append(listing)
            except Exception:
                logger.debug("Skipping unparseable Chrono24 card", exc_info=True)

        return results

    def _parse_card(self, card) -> ScrapedListing | None:
        # --- Link + external_id ---
        link_el = card.select_one("a.js-listing-item-link")
        if not link_el:
            link_el = card.select_one("a[href*='--id']")
        if not link_el:
            return None

        href = link_el.get("href", "")
        if not href:
            return None
        if not href.startswith("http"):
            href = "https://www.chrono24.com" + href

        if "--id" not in href:
            return None
        external_id = href.split("--id")[-1].split(".")[0]
        if not external_id:
            return None

        # --- Title ---
        title_div = card.select_one("div.p-t-3")
        if not title_div:
            return None
        paragraphs = title_div.select("p")
        if not paragraphs:
            return None
        model_name = paragraphs[0].get_text(strip=True)
        subtitle = paragraphs[1].get_text(strip=True) if len(paragraphs) > 1 else ""
        title = f"{model_name} {subtitle}".strip()
        if not title:
            return None

        # --- Price ---
        price_div = card.select_one("div.align-content-end")
        if not price_div:
            return None
        price_text = price_div.get_text(strip=True)
        price_cents = self._parse_price(price_text)
        if not price_cents:
            return None

        # --- Condition ---
        condition = "unknown"
        card_text = card.get_text(" ", strip=True).lower()
        if "new" in card_text and "pre-owned" not in card_text:
            condition = "new"
        elif "pre-owned" in card_text or "pre owned" in card_text:
            condition = "good"
        elif "unworn" in card_text:
            condition = "new"
        elif "very good" in card_text:
            condition = "very good"

        # --- Reference from subtitle ---
        reference = self._try_extract_ref(subtitle) or self._try_extract_ref(title)

        return ScrapedListing(
            source_name=self.source_name,
            external_id=external_id,
            title=title,
            price_usd=price_cents,
            price_type="asking",
            condition=condition,
            listing_url=href.split("?")[0],
            reference_parsed=reference,
            raw_data={"title": title, "url": href, "subtitle": subtitle},
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
    def _try_extract_ref(text: str) -> str | None:
        patterns = [
            r"(?<!\d)(1[12]\d{4}[A-Z]{0,6})(?!\d)",   # Rolex 6-digit refs
            r"(?<!\d)(1[4-9]\d{3}[A-Z]{0,6})(?!\d)",   # Rolex 5-digit refs (older)
            r"\b(5\d{3}[A-Z]?/\d[A-Z]+)\b",           # Patek
            r"(?<!\d)(1[56]\d{3}[A-Z]{2})\b",          # AP Royal Oak
            r"\b(26\d{3}[A-Z]{2})\b",                  # AP Offshore
            r"(\d{3}\.\d{2}\.\d{2}\.\d{2}\.\d{2}\.\d{3})",  # Omega
            r"\b(IW\d{6})\b",                          # IWC
            r"\b(Q\d{7})\b",                           # JLC
            r"(?<!\d)(\d{3}\.\d{3})(?!\d)",            # Lange
            r"\b((?:CR)?W[A-Z]{2,4}\d{4})\b",         # Cartier
            r"(\d{4,5}[A-Z]/\d{3}[A-Z]-[A-Z0-9]{4,5})",  # Vacheron
        ]
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                return m.group(1)
        return None

    def _scrape_via_package(self, query: str) -> list[ScrapedListing]:
        try:
            from chrono24 import query as c24_query  # type: ignore[import-untyped]
        except ImportError:
            logger.warning("chrono24 package not installed")
            return []

        try:
            results = c24_query(query).get_listings(limit=120)
        except Exception:
            logger.exception("chrono24 package query failed for '%s'", query)
            return []

        listings: list[ScrapedListing] = []
        for item in results:
            try:
                price_cents = int(float(item.get("price", 0)) * 100)
                if price_cents <= 0:
                    continue

                listing = ScrapedListing(
                    source_name=self.source_name,
                    external_id=str(item.get("id", item.get("url", ""))),
                    title=item.get("title", ""),
                    price_usd=price_cents,
                    price_type="asking",
                    listing_url=item.get("url"),
                    reference_parsed=item.get("reference_number"),
                    raw_data=item,
                )
                listings.append(listing)
            except Exception:
                logger.debug("Skipping chrono24 package item", exc_info=True)

        logger.info("chrono24 package: %d listings for '%s'", len(listings), query)
        return listings
