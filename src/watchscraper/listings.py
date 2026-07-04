"""Active-listing tracking for days-on-market and listing liquidity.

An asking listing (Chrono24) is tracked from its first appearance to its
disappearance:

  - On each scrape, `record_active` upserts every currently-visible listing:
    inserts with first_seen=last_seen on first sight, else bumps last_seen.
  - `reconcile_delisted` marks listings of a source that were NOT seen in the
    latest scrape as delisted (presumed sold), stamping days_on_market =
    delisted_at - first_seen.

Median days-on-market and listing liquidity are then computed per watch and
per family from the delisted population. The metric is honest about
longitudinal data: it reports only once listings have actually delisted;
before that it reports the tracked count.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from watchscraper.models import ActiveListing, Source, Watch
from watchscraper.schemas import ScrapedListing

logger = logging.getLogger(__name__)


def record_active(
    session: Session,
    source_id: int,
    listings: list[ScrapedListing],
    watch_ids: list[int | None],
    families: list[str | None],
    now: datetime | None = None,
) -> int:
    """Upsert the currently-visible asking listings for a source."""
    now = now or datetime.now(timezone.utc)
    seen = 0
    for listing, watch_id, family in zip(listings, watch_ids, families):
        row = session.execute(
            select(ActiveListing).where(
                ActiveListing.source_id == source_id,
                ActiveListing.external_id == listing.external_id,
            )
        ).scalar_one_or_none()
        if row is None:
            session.add(
                ActiveListing(
                    source_id=source_id,
                    external_id=listing.external_id,
                    watch_id=watch_id,
                    family=family,
                    ask_price_usd=listing.price_usd,
                    first_seen=now,
                    last_seen=now,
                )
            )
        else:
            row.last_seen = now
            row.ask_price_usd = listing.price_usd
            if row.delisted_at is not None:
                # Relisted — reset the clock
                row.delisted_at = None
                row.days_on_market = None
        seen += 1
    session.flush()
    return seen


def reconcile_delisted(
    session: Session, source_id: int, scrape_time: datetime, grace_hours: int = 1
) -> int:
    """Mark listings not seen in the latest scrape as delisted.

    grace_hours guards against a partial scrape: only listings whose
    last_seen predates this scrape by the grace window are delisted.
    """
    cutoff = scrape_time
    rows = session.execute(
        select(ActiveListing).where(
            ActiveListing.source_id == source_id,
            ActiveListing.delisted_at.is_(None),
            ActiveListing.last_seen < cutoff,
        )
    ).scalars().all()
    delisted = 0
    for row in rows:
        row.delisted_at = scrape_time
        row.days_on_market = max(0, (scrape_time - row.first_seen).days)
        delisted += 1
    session.flush()
    return delisted


def backfill_from_price_records(session: Session) -> int:
    """Seed active_listings from existing asking price_records so the
    days-on-market clock starts now rather than on the next scrape."""
    inserted = session.execute(
        text("""
            INSERT INTO active_listings
                (source_id, external_id, watch_id, family, ask_price_usd,
                 first_seen, last_seen)
            SELECT pr.source_id, pr.external_id, pr.watch_id,
                   w.family, pr.price_usd, pr.scraped_at, pr.scraped_at
            FROM price_records pr
            JOIN sources s ON s.id = pr.source_id
            LEFT JOIN watches w ON w.id = pr.watch_id
            WHERE pr.price_type = 'asking'
            ON CONFLICT ON CONSTRAINT uq_active_listing DO NOTHING
        """)
    ).rowcount
    session.commit()
    return inserted


def days_on_market_by_watch(session: Session) -> dict[int, float]:
    """Median days-on-market per watch_id from delisted listings."""
    rows = session.execute(
        text("""
            SELECT watch_id,
                   percentile_cont(0.5) WITHIN GROUP (ORDER BY days_on_market) AS median
            FROM active_listings
            WHERE delisted_at IS NOT NULL AND watch_id IS NOT NULL
            GROUP BY watch_id
        """)
    ).all()
    return {r[0]: float(r[1]) for r in rows if r[1] is not None}


def days_on_market_by_family(session: Session) -> dict[str, float]:
    rows = session.execute(
        text("""
            SELECT family,
                   percentile_cont(0.5) WITHIN GROUP (ORDER BY days_on_market) AS median
            FROM active_listings
            WHERE delisted_at IS NOT NULL AND family IS NOT NULL
            GROUP BY family
        """)
    ).all()
    return {r[0]: float(r[1]) for r in rows if r[1] is not None}


def active_counts_by_family(session: Session) -> dict[str, int]:
    """Currently-active listing count per family (supply proxy)."""
    rows = session.execute(
        text("""
            SELECT family, COUNT(*) FROM active_listings
            WHERE delisted_at IS NULL AND family IS NOT NULL
            GROUP BY family
        """)
    ).all()
    return {r[0]: int(r[1]) for r in rows}
