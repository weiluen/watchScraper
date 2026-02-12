"""One-time backfill: re-link price_records to watches.

Two passes:
1. Re-parse reference_parsed from title where it's NULL (using improved regex).
2. Re-resolve watch_id for all records where watch_id IS NULL.

Uses raw SQL to avoid ORM enum deserialization issues.
"""

import logging
import re

from sqlalchemy import text

from watchscraper.database import get_session
from watchscraper.models import Watch, WatchAlias
from watchscraper.normalizers.reference import normalize_reference, resolve_alias
from sqlalchemy import select

logger = logging.getLogger(__name__)

# Same patterns used in eBay/Chrono24 scrapers
_REF_PATTERNS = [
    r"(?<!\d)(1[12]\d{4}[A-Z]{0,6})(?!\d)",        # Rolex 6-digit
    r"(?<!\d)(1[4-9]\d{3}[A-Z]{0,6})(?!\d)",        # Rolex 5-digit
    r"\b(5\d{3}[A-Z]?/\d[A-Z]+)\b",                 # Patek
    r"(?<!\d)(1[56]\d{3}[A-Z]{2})\b",               # AP Royal Oak
    r"\b(26\d{3}[A-Z]{2})\b",                       # AP Offshore
    r"(\d{3}\.\d{2}\.\d{2}\.\d{2}\.\d{2}\.\d{3})",  # Omega dotted
    r"\b(IW\d{6})\b",                               # IWC
    r"\b(Q\d{7})\b",                                # JLC
    r"(?<!\d)(\d{3}\.\d{3})(?!\d)",                  # Lange
    r"\b((?:CR)?W[A-Z]{2,4}\d{4})\b",               # Cartier
    r"(\d{4,5}[A-Z]/\d{3}[A-Z]-[A-Z0-9]{4,5})",    # Vacheron
]


def _try_extract_ref(text_str: str) -> str | None:
    for pat in _REF_PATTERNS:
        m = re.search(pat, text_str, re.IGNORECASE)
        if m:
            return m.group(1)
    return None


def _resolve_watch_id(session, ref: str) -> int | None:
    """Try to match a reference string to a watch_id."""
    # Alias lookup
    canonical = resolve_alias(ref)
    if canonical:
        alias_row = session.execute(
            select(WatchAlias).where(WatchAlias.alias == canonical)
        ).scalar_one_or_none()
        if alias_row:
            return alias_row.watch_id

    # Direct reference match
    normalized = normalize_reference(ref)
    watch = session.execute(
        select(Watch).where(Watch.reference_number == normalized)
    ).scalar_one_or_none()
    if watch:
        return watch.id

    return None


def run_backfill() -> None:
    session = get_session()
    try:
        # === Pass 1: Re-parse reference_parsed from title ===
        rows = session.execute(
            text("SELECT id, title FROM price_records WHERE reference_parsed IS NULL AND title IS NOT NULL")
        ).fetchall()

        parsed_count = 0
        for rec_id, title in rows:
            ref = _try_extract_ref(title)
            if ref:
                session.execute(
                    text("UPDATE price_records SET reference_parsed = :ref WHERE id = :id"),
                    {"ref": ref, "id": rec_id},
                )
                parsed_count += 1

        logger.info("Pass 1: Parsed reference from title for %d / %d records", parsed_count, len(rows))
        session.flush()

        # === Pass 2: Re-resolve watch_id for all unlinked records ===
        rows = session.execute(
            text("SELECT id, reference_parsed FROM price_records WHERE watch_id IS NULL AND reference_parsed IS NOT NULL")
        ).fetchall()

        linked_count = 0
        for rec_id, ref in rows:
            watch_id = _resolve_watch_id(session, ref)
            if watch_id:
                session.execute(
                    text("UPDATE price_records SET watch_id = :wid WHERE id = :id"),
                    {"wid": watch_id, "id": rec_id},
                )
                linked_count += 1

        logger.info("Pass 2: Linked %d / %d records to watches", linked_count, len(rows))

        session.commit()

        # Summary
        total = session.execute(text("SELECT COUNT(*) FROM price_records")).scalar()
        linked_total = session.execute(
            text("SELECT COUNT(*) FROM price_records WHERE watch_id IS NOT NULL")
        ).scalar()
        logger.info(
            "Backfill complete: %d / %d records linked (%.1f%%)",
            linked_total, total, 100 * linked_total / total,
        )

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    run_backfill()
