import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from watchscraper.database import get_session
from watchscraper.dedup import get_existing_external_ids
from watchscraper.matching import Matcher
from watchscraper.models import (
    PriceRecord,
    ScrapeRun,
    ScrapeRunStatus,
    Source,
    Watch,
    WatchAlias,
)
from watchscraper.normalizers.reference import normalize_reference, resolve_alias
from watchscraper.schemas import ScrapedListing
from watchscraper.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


def _get_or_create_source(session: Session, scraper: BaseScraper) -> Source:
    source = session.execute(
        select(Source).where(Source.name == scraper.source_name)
    ).scalar_one_or_none()

    if source is None:
        source = Source(
            name=scraper.source_name,
            base_url=_source_url(scraper.source_name),
            scraper_type=type(scraper).__name__,
            is_active=True,
        )
        session.add(source)
        session.flush()

    return source


def _source_url(name: str) -> str:
    urls = {
        "ebay": "https://www.ebay.com",
        "chrono24": "https://www.chrono24.com",
        "watchcharts": "https://watchcharts.com",
        "hodinkee": "https://shop.hodinkee.com",
    }
    return urls.get(name, "")


def _resolve_watch_id(session: Session, listing: ScrapedListing) -> int | None:
    """Try to match a listing to a canonical watch via reference or alias."""
    ref = listing.reference_parsed
    if not ref:
        return None

    # Try direct alias lookup
    canonical = resolve_alias(ref)
    if canonical:
        alias_row = session.execute(
            select(WatchAlias).where(WatchAlias.alias == canonical)
        ).scalar_one_or_none()
        if alias_row:
            return alias_row.watch_id

    # Try matching against watches table
    normalized = normalize_reference(ref)
    watch = session.execute(
        select(Watch).where(Watch.reference_number == normalized)
    ).scalar_one_or_none()
    if watch:
        return watch.id

    return None


def run_pipeline(
    scraper: BaseScraper,
    query: str,
    **scrape_kwargs,
) -> int:
    """Execute the full scrape → normalize → dedupe → insert pipeline.

    Returns the number of new records inserted.
    """
    session = get_session()
    source = _get_or_create_source(session, scraper)

    # Start scrape run
    run = ScrapeRun(
        source_id=source.id,
        status=ScrapeRunStatus.RUNNING,
    )
    session.add(run)
    session.commit()

    try:
        # 1. Scrape
        listings = scraper.scrape(query, **scrape_kwargs)
        run.records_scraped = len(listings)
        logger.info("Scraped %d listings from %s", len(listings), scraper.source_name)

        if not listings:
            run.status = ScrapeRunStatus.SUCCESS
            run.finished_at = datetime.now(timezone.utc)
            session.commit()
            return 0

        # 2. Deduplicate — within batch + against DB
        seen_ids: set[str] = set()
        unique_listings: list[ScrapedListing] = []
        for l in listings:
            if l.external_id not in seen_ids:
                seen_ids.add(l.external_id)
                unique_listings.append(l)

        all_ext_ids = [l.external_id for l in unique_listings]
        existing_ids = get_existing_external_ids(
            session, scraper.source_name, all_ext_ids
        )
        new_listings = [
            l for l in unique_listings if l.external_id not in existing_ids
        ]
        logger.info(
            "After dedup: %d new / %d total", len(new_listings), len(listings)
        )

        # 3. Match to references + insert
        matcher = Matcher.from_session(session)
        inserted = 0
        for listing in new_listings:
            match = matcher.match(listing.title, query=query)

            record = PriceRecord(
                watch_id=match.watch_id,
                source_id=source.id,
                price_usd=listing.price_usd,
                price_type=listing.price_type,
                condition=listing.condition,
                has_box=listing.has_box,
                has_papers=listing.has_papers,
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
            session.add(record)
            inserted += 1

        # Track active asking listings for days-on-market / liquidity.
        # Applies to the full de-duplicated batch (not just new rows): a
        # listing still present is a listing still on the market.
        if unique_listings and unique_listings[0].price_type == "asking":
            from watchscraper.listings import record_active, reconcile_delisted

            scrape_time = datetime.now(timezone.utc)
            watch_ids = [_resolve_watch_id(session, l) for l in unique_listings]
            fams: list[str | None] = []
            for wid in watch_ids:
                fam = None
                if wid is not None:
                    w = session.get(Watch, wid)
                    fam = w.family if w else None
                fams.append(fam)
            record_active(session, source.id, unique_listings, watch_ids, fams, scrape_time)
            delisted = reconcile_delisted(session, source.id, scrape_time)
            logger.info(
                "Active listings: %d tracked, %d delisted", len(unique_listings), delisted
            )

        run.records_inserted = inserted
        run.status = ScrapeRunStatus.SUCCESS
        run.finished_at = datetime.now(timezone.utc)
        session.commit()

        logger.info("Inserted %d new records into price_records", inserted)
        return inserted

    except Exception as e:
        run.status = ScrapeRunStatus.FAILED
        run.error_message = str(e)[:2000]
        run.finished_at = datetime.now(timezone.utc)
        session.commit()
        logger.exception("Pipeline failed for %s", scraper.source_name)
        raise
    finally:
        session.close()
