import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from watchscraper.models import PriceRecord, Source

logger = logging.getLogger(__name__)


def get_existing_external_ids(
    session: Session, source_name: str, external_ids: list[str]
) -> set[str]:
    """Return the subset of external_ids that already exist in price_records
    for the given source. Used to skip duplicates before insertion."""
    if not external_ids:
        return set()

    source = session.execute(
        select(Source).where(Source.name == source_name)
    ).scalar_one_or_none()

    if source is None:
        return set()

    stmt = (
        select(PriceRecord.external_id)
        .where(PriceRecord.source_id == source.id)
        .where(PriceRecord.external_id.in_(external_ids))
    )
    rows = session.execute(stmt).scalars().all()
    existing = set(rows)

    if existing:
        logger.info(
            "Dedup: %d/%d already exist for source '%s'",
            len(existing),
            len(external_ids),
            source_name,
        )

    return existing
