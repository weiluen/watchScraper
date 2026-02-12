import logging
import re
from datetime import datetime, timezone
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from watchscraper.schemas import ScrapedListing
from watchscraper.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class EbayScraper(BaseScraper):
    """Scrape eBay sold/completed listings for real transaction prices."""

    source_name = "ebay"

    SOLD_URL = (
        "https://www.ebay.com/sch/i.html"
        "?_nkw={query}"
        "&_sacat=31387"          # Wristwatches category
        "&LH_Sold=1"            # Sold items only
        "&LH_Complete=1"        # Completed listings
        "&_sop=13"              # Sort: end date newest first
        "&_ipg=120"             # 120 results per page
    )

    def scrape(self, query: str, max_pages: int = 3, **kwargs) -> list[ScrapedListing]:
        # Try Playwright first (eBay blocks plain requests with 503)
        listings = self._scrape_playwright(query, max_pages)
        if listings:
            return listings

        # Fallback to requests (may work with some UAs/IPs)
        logger.info("Playwright unavailable, falling back to requests")
        return self._scrape_requests(query, max_pages)

    # Chromium launch args to minimize memory usage (~180MB vs ~580MB default)
    _CHROMIUM_ARGS = [
        "--disable-gpu",
        "--disable-dev-shm-usage",
        "--disable-extensions",
        "--no-sandbox",
        "--single-process",
        "--disable-software-rasterizer",
        "--js-flags=--max-old-space-size=128",
    ]

    def _scrape_playwright(self, query: str, max_pages: int) -> list[ScrapedListing]:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.warning("Playwright not installed — cannot scrape eBay")
            return []

        listings: list[ScrapedListing] = []
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(
                    headless=True, args=self._CHROMIUM_ARGS
                )
                context = browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/131.0.0.0 Safari/537.36"
                    )
                )
                page = context.new_page()

                for pg in range(1, max_pages + 1):
                    url = self.SOLD_URL.format(query=quote_plus(query))
                    if pg > 1:
                        url += f"&_pgn={pg}"

                    logger.info("eBay Playwright page %d: %s", pg, url)
                    page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_timeout(2000)

                    html = page.content()
                    page_listings = self._parse_results(html)
                    if not page_listings:
                        logger.info("No listings on page %d, stopping", pg)
                        break
                    listings.extend(page_listings)
                    logger.info(
                        "Parsed %d listings from eBay page %d",
                        len(page_listings),
                        pg,
                    )
                    self._delay()

                browser.close()
        except Exception:
            logger.exception("eBay Playwright scrape failed")

        logger.info("eBay total: %d listings for '%s'", len(listings), query)
        return listings

    def _scrape_requests(self, query: str, max_pages: int) -> list[ScrapedListing]:
        listings: list[ScrapedListing] = []
        for page in range(1, max_pages + 1):
            url = self.SOLD_URL.format(query=quote_plus(query))
            if page > 1:
                url += f"&_pgn={page}"

            logger.info("eBay page %d: %s", page, url)
            try:
                resp = self._get(url)
            except Exception:
                logger.exception("Failed to fetch eBay page %d", page)
                break

            page_listings = self._parse_results(resp.text)
            if not page_listings:
                break
            listings.extend(page_listings)
            logger.info("Parsed %d listings from page %d", len(page_listings), page)

        logger.info("eBay total: %d listings for '%s'", len(listings), query)
        return listings

    def _parse_results(self, html: str) -> list[ScrapedListing]:
        soup = BeautifulSoup(html, "lxml")

        # New eBay layout: li.s-card inside ul.srp-results
        items = soup.select("ul.srp-results > li.s-card")
        if not items:
            # Legacy layout fallback
            items = soup.select("div.s-item__wrapper")

        results: list[ScrapedListing] = []
        for item in items:
            try:
                listing = self._parse_item(item)
                if listing:
                    results.append(listing)
            except Exception:
                logger.debug("Skipping unparseable eBay item", exc_info=True)

        return results

    def _parse_item(self, item) -> ScrapedListing | None:
        # --- Title ---
        # New layout: a.s-card__title, or any link with /itm/ in href
        title_el = item.select_one("a.s-card__title")
        if not title_el:
            title_el = item.select_one("div.s-item__title span[role='heading']")
        if not title_el:
            title_el = item.select_one("div.s-item__title")
        if not title_el:
            # Try any link containing /itm/
            for a in item.select("a[href*='/itm/']"):
                text = a.get_text(strip=True)
                if text and len(text) > 10:
                    title_el = a
                    break
        if not title_el:
            return None
        title = title_el.get_text(strip=True)
        if title.lower().startswith("shop on ebay"):
            return None
        # Strip "Opens in a new window or tab" suffix
        title = re.sub(r"Opens in a new (?:window|tab).*$", "", title).strip()

        # --- Link + external_id ---
        link_el = item.select_one("a[href*='/itm/']")
        if not link_el:
            link_el = item.select_one("a.s-item__link")
        if not link_el:
            return None
        url = link_el.get("href", "")
        external_id = self._extract_item_id(url)
        if not external_id:
            return None

        # --- Price ---
        # New layout: span.s-card__price
        price_el = item.select_one("span.s-card__price")
        if not price_el:
            price_el = item.select_one("span.s-item__price")
        if not price_el:
            return None
        price_cents = self._parse_price(price_el.get_text(strip=True))
        if not price_cents:
            return None

        # --- Date sold ---
        observed_at = None
        # New layout: "Sold  Feb 8, 2026" appears in card text
        sold_el = item.select_one("span.s-card__sold-date, span.s-card__ended-date")
        if sold_el:
            observed_at = self._parse_date(sold_el.get_text(strip=True))
        if not observed_at:
            # Try extracting from card text
            card_text = item.get_text(" ", strip=True)
            sold_match = re.search(r"Sold\s+(\w+ \d{1,2},? \d{4})", card_text)
            if sold_match:
                observed_at = self._parse_date(sold_match.group(1))
        if not observed_at:
            date_el = item.select_one(
                "span.s-item__ended-date, span.s-item__endedDate"
            )
            if date_el:
                observed_at = self._parse_date(date_el.get_text(strip=True))

        # --- Condition ---
        condition = "unknown"
        card_text = item.get_text(" ", strip=True).lower()
        if "brand new" in card_text or "new with" in card_text:
            condition = "new"
        elif "pre-owned" in card_text or "pre owned" in card_text:
            condition = "good"
        else:
            cond_el = item.select_one("span.SECONDARY_INFO")
            if cond_el:
                condition = self._normalize_condition(cond_el.get_text(strip=True))

        return ScrapedListing(
            source_name=self.source_name,
            external_id=external_id,
            title=title,
            price_usd=price_cents,
            price_type="sold",
            condition=condition,
            listing_url=url.split("?")[0] if url else None,
            observed_at=observed_at,
            reference_parsed=self._try_extract_ref(title),
            raw_data={"title": title, "url": url},
        )

    @staticmethod
    def _extract_item_id(url: str) -> str | None:
        m = re.search(r"/itm/(\d+)", url)
        return m.group(1) if m else None

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
    def _parse_date(text: str) -> datetime | None:
        # eBay formats: "Feb 1, 2026" or "Jan-01 12:30"
        for fmt in ("%b %d, %Y", "%b-%d %H:%M", "%d %b, %Y"):
            try:
                dt = datetime.strptime(text.strip(), fmt)
                if dt.year < 2000:
                    dt = dt.replace(year=datetime.now().year)
                return dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        return None

    @staticmethod
    def _normalize_condition(text: str) -> str:
        t = text.lower()
        if "new" in t:
            return "new"
        if "pre-owned" in t or "pre owned" in t:
            return "good"
        return "unknown"

    @staticmethod
    def _try_extract_ref(title: str) -> str | None:
        """Best-effort reference number extraction from listing title."""
        patterns = [
            r"(?<!\d)(1[12]\d{4}[A-Z]{0,6})(?!\d)",   # Rolex 6-digit refs
            r"(?<!\d)(1[4-9]\d{3}[A-Z]{0,6})(?!\d)",   # Rolex 5-digit refs (older)
            r"\b(5\d{3}[A-Z]?/\d[A-Z]+)\b",           # Patek "5711/1A" style
            r"(?<!\d)(1[56]\d{3}[A-Z]{2})\b",          # AP Royal Oak refs
            r"\b(26\d{3}[A-Z]{2})\b",                  # AP Royal Oak Offshore
            r"(\d{3}\.\d{2}\.\d{2}\.\d{2}\.\d{2}\.\d{3})",  # Omega dotted
            r"\b(IW\d{6})\b",                          # IWC
            r"\b(Q\d{7})\b",                           # JLC
            r"(?<!\d)(\d{3}\.\d{3})(?!\d)",            # A. Lange & Söhne
            r"\b((?:CR)?W[A-Z]{2,4}\d{4})\b",         # Cartier
            r"(\d{4,5}[A-Z]/\d{3}[A-Z]-[A-Z0-9]{4,5})",  # Vacheron Constantin
        ]
        for pat in patterns:
            m = re.search(pat, title, re.IGNORECASE)
            if m:
                return m.group(1)
        return None
