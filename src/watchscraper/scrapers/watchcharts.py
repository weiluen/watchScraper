import logging
import re
import time
from datetime import datetime, timezone

from watchscraper.config import settings
from watchscraper.schemas import ScrapedListing
from watchscraper.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class WatchChartsScraper(BaseScraper):
    """Fetch estimated market values from the WatchCharts v3 REST API.

    Uses api.watchcharts.com/v3 with x-api-key auth and curl_cffi
    for TLS fingerprint compatibility.

    Workflow: search by brand + reference → get UUID → fetch watch info/history.
    Rate limited to 1 req/sec. Metered by data credits.
    """

    source_name = "watchcharts"
    BASE_URL = "https://api.watchcharts.com/v3"

    # Credit costs per endpoint (from docs):
    # /search/watch: 1, /watch/info: 3, /watch/price_1y: 3,
    # /watch/price_5y: 8, /watch/price_full: 10, /watch/retail: 5,
    # /watch/specs: 10, /watch/listings: 5, /watch/appraisal: 5,
    # /brand/list: 1

    # Map our brand slugs/names to WatchCharts brand names
    BRAND_MAP: dict[str, str] = {
        "rolex": "Rolex",
        "audemars-piguet": "Audemars Piguet",
        "ap": "Audemars Piguet",
        "patek-philippe": "Patek Philippe",
        "patek": "Patek Philippe",
        "omega": "Omega",
        "vacheron-constantin": "Vacheron Constantin",
        "vacheron": "Vacheron Constantin",
        "iwc": "IWC",
        "jaeger-lecoultre": "Jaeger-LeCoultre",
        "jaeger": "Jaeger-LeCoultre",
        "a-lange-sohne": "A. Lange & Söhne",
        "lange": "A. Lange & Söhne",
        "cartier": "Cartier",
    }

    def __init__(self) -> None:
        super().__init__()
        self._last_request_time = 0.0

    def scrape(self, query: str, **kwargs) -> list[ScrapedListing]:
        if not settings.watchcharts_api_key:
            logger.warning("WATCHCHARTS_API_KEY not set — skipping WatchCharts")
            return []

        brand_name, reference = self._parse_query(query)
        if not brand_name or not reference:
            logger.warning(
                "WatchCharts requires brand + reference. "
                "Could not parse from query '%s'",
                query,
            )
            return []

        uuid = self._search(brand_name, reference)
        if not uuid:
            logger.info("WatchCharts: no results for '%s %s'", brand_name, reference)
            return []

        listing = self._get_watch_info(uuid, reference)
        if listing:
            return [listing]
        return []

    def _api_get(self, path: str, params: dict | None = None) -> dict | None:
        """Make a rate-limited GET to the WatchCharts v3 API via curl_cffi."""
        try:
            from curl_cffi import requests as cffi_requests
        except ImportError:
            logger.error("curl_cffi required for WatchCharts — pip install curl_cffi")
            return None

        # Enforce 1 req/sec rate limit
        elapsed = time.monotonic() - self._last_request_time
        if elapsed < 1.1:
            time.sleep(1.1 - elapsed)

        url = f"{self.BASE_URL}{path}"
        headers = {
            "x-api-key": settings.watchcharts_api_key,
            "Accept": "application/json",
        }

        try:
            resp = cffi_requests.get(
                url,
                params=params or {},
                headers=headers,
                impersonate="chrome",
                timeout=20,
            )
            self._last_request_time = time.monotonic()

            if resp.status_code != 200:
                logger.warning(
                    "WatchCharts %s returned %d: %s",
                    path,
                    resp.status_code,
                    resp.text[:200],
                )
                return None

            return resp.json()
        except Exception:
            logger.exception("WatchCharts request failed: %s", path)
            self._last_request_time = time.monotonic()
            return None

    def _search(self, brand_name: str, reference: str) -> str | None:
        """Search for a watch UUID by brand + reference. Returns UUID or None."""
        data = self._api_get(
            "/search/watch",
            params={"brand_name": brand_name, "reference": reference},
        )
        if not data or not data.get("success"):
            return None

        results = data.get("results", [])
        if not results:
            return None

        # Take the highest-confidence match
        best = max(results, key=lambda r: r.get("confidence", 0))
        uuid = best.get("uuid")
        logger.info(
            "WatchCharts search: %s %s → uuid=%s (confidence=%d)",
            brand_name,
            reference,
            uuid,
            best.get("confidence", 0),
        )
        return uuid

    def _get_watch_info(self, uuid: str, reference: str) -> ScrapedListing | None:
        """Fetch current market value for a watch UUID."""
        data = self._api_get("/watch/info", params={"uuid": uuid, "currency": "USD"})
        if not data:
            return None

        price = data.get("market_price")
        if not price:
            return None

        price_cents = int(float(price) * 100)
        if price_cents <= 0:
            return None

        brand = data.get("brand", "")
        collection = data.get("collection", "")
        model = data.get("model", reference)
        title = f"{brand} {collection} {model}".strip()

        return ScrapedListing(
            source_name=self.source_name,
            external_id=f"wc-{uuid}",
            title=title,
            price_usd=price_cents,
            price_type="estimated",
            reference_parsed=model,
            observed_at=datetime.fromisoformat(data["updated"]).replace(
                tzinfo=timezone.utc
            )
            if data.get("updated")
            else datetime.now(timezone.utc),
            raw_data={
                "uuid": uuid,
                "market_price": data.get("market_price"),
                "dealer_price": data.get("dealer_price"),
                "volatility": data.get("volatility"),
                "brand": brand,
                "collection": collection,
                "model": model,
            },
        )

    def get_historical(
        self, uuid: str, days: int = 365
    ) -> list[ScrapedListing]:
        """Pull historical daily market values for backfill.

        Uses /watch/price_1y (3 credits) for <=365 days,
        /watch/price_5y (8 credits) for <=1825 days,
        /watch/price_full (10 credits) otherwise.
        """
        if not settings.watchcharts_api_key:
            return []

        if days <= 365:
            path = "/watch/price_1y"
        elif days <= 1825:
            path = "/watch/price_5y"
        else:
            path = "/watch/price_full"

        data = self._api_get(path, params={"uuid": uuid, "currency": "USD"})
        if not data:
            return []

        listings: list[ScrapedListing] = []
        # API returns {date_str: {price, volatility}, ...}
        for date_str, entry in data.items():
            try:
                if not isinstance(entry, dict):
                    continue
                price = entry.get("price")
                if not price:
                    continue
                price_cents = int(float(price) * 100)
                if price_cents <= 0:
                    continue

                observed_at = datetime.fromisoformat(date_str).replace(
                    tzinfo=timezone.utc
                )

                listings.append(
                    ScrapedListing(
                        source_name=self.source_name,
                        external_id=f"wc-{uuid}-{date_str}",
                        title=str(uuid),
                        price_usd=price_cents,
                        price_type="estimated",
                        observed_at=observed_at,
                        raw_data={"uuid": uuid, "date": date_str, **entry},
                    )
                )
            except Exception:
                logger.debug("Skipping WatchCharts history entry", exc_info=True)

        logger.info(
            "WatchCharts history: %d data points for %s (%s)",
            len(listings),
            uuid,
            path,
        )
        return listings

    def get_brand_list(self) -> list[dict]:
        """Fetch list of supported brands from the API."""
        data = self._api_get("/brand/list")
        return data if isinstance(data, list) else []

    def _parse_query(self, query: str) -> tuple[str | None, str | None]:
        """Extract brand name and reference number from a search query.

        Expects queries like:
        - "Rolex Submariner 126610LN"
        - "Rolex 126610LN"
        - "Audemars Piguet Royal Oak 15500ST"
        """
        query_lower = query.lower().strip()

        # Try to match a known brand
        brand_name = None
        remainder = query

        # Sort by length descending so "Audemars Piguet" matches before "AP"
        for key in sorted(self.BRAND_MAP, key=len, reverse=True):
            if query_lower.startswith(key):
                brand_name = self.BRAND_MAP[key]
                remainder = query[len(key):].strip()
                break
            # Also try the display name
            display = self.BRAND_MAP[key]
            if query_lower.startswith(display.lower()):
                brand_name = display
                remainder = query[len(display):].strip()
                break

        if not brand_name:
            return None, None

        # Extract reference from the remainder
        # Try common reference patterns
        ref_patterns = [
            r"(1[12]\d{4}[A-Z]{0,6})",       # Rolex 6-digit
            r"(1[4-9]\d{3}[A-Z]{0,6})",       # Rolex 5-digit
            r"(5\d{3}[A-Z]?/\d[A-Z]+)",       # Patek
            r"(1[56]\d{3}[A-Z]{2})",           # AP Royal Oak
            r"(26\d{3}[A-Z]{2})",              # AP Offshore
            r"(\d{3}\.\d{2}\.\d{2}\.\d{2}\.\d{2}\.\d{3})",  # Omega
            r"(IW\d{6})",                       # IWC
            r"(Q\d{7})",                        # JLC
            r"(\d{3}\.\d{3})",                  # Lange
            r"((?:CR)?W[A-Z]{2,4}\d{4})",      # Cartier
            r"(\d{4,5}[A-Z]/\d{3}[A-Z]-[A-Z0-9]{4,5})",  # Vacheron
        ]
        for pat in ref_patterns:
            m = re.search(pat, remainder, re.IGNORECASE)
            if m:
                return brand_name, m.group(1)

        # Fallback: last word might be the reference
        words = remainder.split()
        if words:
            return brand_name, words[-1]

        return brand_name, None
