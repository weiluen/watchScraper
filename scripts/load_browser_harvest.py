"""Load eBay sold listings harvested via the browser into price_records.

Input: a JSON array of compact records exported by the in-browser harvester:
  {"q": query, "id": ebay_item_id, "t": title, "p": "$1,234.00",
   "d": "Jun 20, 2026", "c": "new"|"good"|"unknown"}

Reuses the eBay scraper's parsing helpers and the pipeline's watch resolution
so records are indistinguishable from ones scraped directly.
"""

import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from watchscraper.database import get_session
from watchscraper.dedup import get_existing_external_ids
from watchscraper.matching import Matcher
from watchscraper.models import PriceRecord, Source
from watchscraper.schemas import ScrapedListing
from watchscraper.scrapers.ebay import EbayScraper

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def parse_record(raw: dict) -> ScrapedListing | None:
    title = re.sub(r"Opens in a new (?:window|tab).*$", "", raw.get("t", "")).strip()
    if not title or not raw.get("id") or not raw.get("p"):
        return None

    price_cents = EbayScraper._parse_price(raw["p"])
    if not price_cents:
        return None

    observed_at = None
    if raw.get("d"):
        try:
            observed_at = datetime.strptime(raw["d"].replace(",", ""), "%b %d %Y").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            pass

    return ScrapedListing(
        source_name="ebay",
        external_id=raw["id"],
        title=title,
        price_usd=price_cents,
        price_type="sold",
        condition=raw.get("c", "unknown"),
        listing_url=f"https://www.ebay.com/itm/{raw['id']}",
        observed_at=observed_at,
        reference_parsed=EbayScraper._try_extract_ref(title),
        raw_data={"query": raw.get("q"), "title": title},
    )


def run_load(path: str) -> None:
    records = json.loads(Path(path).read_text())
    logger.info("Loaded %d raw records from %s", len(records), path)

    listings: dict[str, ScrapedListing] = {}
    for raw in records:
        listing = parse_record(raw)
        if listing and listing.external_id not in listings:
            listings[listing.external_id] = listing
    logger.info("Parsed %d unique listings", len(listings))

    session = get_session()
    try:
        source = session.query(Source).filter_by(name="ebay").one_or_none()
        if source is None:
            source = Source(
                name="ebay",
                base_url="https://www.ebay.com",
                scraper_type="EbayScraper",
                is_active=True,
            )
            session.add(source)
            session.flush()

        existing = get_existing_external_ids(session, "ebay", list(listings.keys()))
        new_listings = [l for l in listings.values() if l.external_id not in existing]
        logger.info("%d new after dedup against DB", len(new_listings))

        matcher = Matcher.from_session(session)
        linked = 0
        for listing in new_listings:
            query = (listing.raw_data or {}).get("query")
            match = matcher.match(listing.title, query=query)
            if match.watch_id:
                linked += 1
            session.add(
                PriceRecord(
                    watch_id=match.watch_id,
                    source_id=source.id,
                    price_usd=listing.price_usd,
                    price_type=listing.price_type,
                    condition=listing.condition,
                    listing_url=listing.listing_url,
                    external_id=listing.external_id,
                    title=listing.title,
                    reference_parsed=listing.reference_parsed,
                    match_method=match.method,
                    match_confidence=match.confidence,
                    parsed_year=listing.parsed_year,
                    parsed_attributes=listing.parsed_attributes,
                    observed_at=listing.observed_at,
                    raw_data=listing.raw_data,
                )
            )
        session.commit()
        logger.info(
            "Inserted %d records (%d linked to a reference watch, %.1f%%)",
            len(new_listings),
            linked,
            100.0 * linked / len(new_listings) if new_listings else 0.0,
        )
    finally:
        session.close()


if __name__ == "__main__":
    run_load(sys.argv[1] if len(sys.argv) > 1 else str(Path.home() / "Downloads" / "ebay_harvest.json"))
