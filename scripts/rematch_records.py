"""Re-run the matching rules engine over every price record.

Updates watch_id, match_method, match_confidence, parsed_year, and
parsed_attributes in place, then prints before/after link statistics and a
per-method breakdown. Idempotent — safe to re-run after catalog updates.
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from watchscraper.database import get_session
from watchscraper.matching import Matcher, extract_attributes
from watchscraper.models import PriceRecord

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BATCH = 1000


def run_rematch() -> None:
    session = get_session()
    try:
        matcher = Matcher.from_session(session)
        logger.info(
            "Catalog: %d references, %d nicknames",
            len(matcher.entries),
            len(matcher.nicknames),
        )

        records = session.execute(select(PriceRecord)).scalars().all()
        before_linked = sum(1 for r in records if r.watch_id is not None)

        methods: dict[str, int] = {}
        changed = 0
        for i, record in enumerate(records, 1):
            query = (record.raw_data or {}).get("query")
            match = matcher.match(record.title or "", query=query)

            attrs = extract_attributes(record.title or "")
            if (
                record.watch_id != match.watch_id
                or record.match_method != match.method
            ):
                changed += 1
            record.watch_id = match.watch_id
            record.match_method = match.method
            record.match_confidence = match.confidence
            record.parsed_year = attrs.get("year")
            record.parsed_attributes = attrs or None

            methods[match.method] = methods.get(match.method, 0) + 1
            if i % BATCH == 0:
                session.flush()
                logger.info("...%d/%d", i, len(records))

        session.commit()

        after_linked = sum(1 for r in records if r.watch_id is not None)
        total = len(records)
        logger.info("Records: %d | changed: %d", total, changed)
        logger.info(
            "Linked to a reference: %d (%.1f%%) -> %d (%.1f%%)",
            before_linked, 100 * before_linked / total,
            after_linked, 100 * after_linked / total,
        )
        logger.info("By method:")
        for method, count in sorted(methods.items(), key=lambda kv: -kv[1]):
            logger.info("  %-22s %5d (%.1f%%)", method, count, 100 * count / total)
    finally:
        session.close()


if __name__ == "__main__":
    run_rematch()
