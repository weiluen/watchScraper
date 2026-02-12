import logging
import time
from datetime import datetime, timezone

from apscheduler.schedulers.blocking import BlockingScheduler

from watchscraper.pipeline import run_pipeline
from watchscraper.scrapers.chrono24 import Chrono24Scraper
from watchscraper.scrapers.ebay import EbayScraper

logger = logging.getLogger(__name__)

# Full query list across all 9 brands (matches cli.py _build_queries)
DEFAULT_QUERIES = [
    # Rolex
    "Rolex Submariner",
    "Rolex Daytona",
    "Rolex GMT-Master II",
    "Rolex Datejust 41",
    "Rolex Explorer",
    "Rolex Sky-Dweller",
    # Audemars Piguet
    "Audemars Piguet Royal Oak",
    "Audemars Piguet Royal Oak Offshore",
    # Patek Philippe
    "Patek Philippe Nautilus",
    "Patek Philippe Aquanaut",
    "Patek Philippe Calatrava",
    # Omega
    "Omega Speedmaster",
    "Omega Seamaster 300M",
    "Omega Seamaster Aqua Terra",
    "Omega Seamaster Planet Ocean",
    # Vacheron Constantin
    "Vacheron Constantin Overseas",
    "Vacheron Constantin Patrimony",
    "Vacheron Constantin Traditionnelle",
    "Vacheron Constantin Fiftysix",
    # IWC
    "IWC Portugieser",
    "IWC Big Pilot",
    "IWC Pilot Mark",
    "IWC Aquatimer",
    # Jaeger-LeCoultre
    "Jaeger-LeCoultre Reverso",
    "Jaeger-LeCoultre Master Ultra Thin",
    "Jaeger-LeCoultre Polaris",
    # A. Lange & Söhne
    "A. Lange Sohne Lange 1",
    "A. Lange Sohne Saxonia",
    "A. Lange Sohne Datograph",
    "A. Lange Sohne 1815",
    # Cartier
    "Cartier Santos",
    "Cartier Tank",
    "Cartier Ballon Bleu",
    "Cartier Pasha",
]

# Delay between queries per source (seconds) to avoid rate-limiting
_QUERY_DELAYS = {
    "chrono24": 5,
    "ebay": 2,
}

SCRAPERS = {
    "ebay": EbayScraper,
    "chrono24": Chrono24Scraper,
}


def _run_source(source_name: str) -> None:
    """Run all default queries for a single source."""
    scraper_cls = SCRAPERS.get(source_name)
    if not scraper_cls:
        logger.error("Unknown source: %s", source_name)
        return

    delay = _QUERY_DELAYS.get(source_name, 2)
    scraper = scraper_cls()
    total_inserted = 0
    start = time.monotonic()

    for i, query in enumerate(DEFAULT_QUERIES):
        if i > 0:
            time.sleep(delay)
        try:
            count = run_pipeline(scraper, query)
            total_inserted += count
            logger.info(
                "Scheduled %s / '%s': %d records", source_name, query, count
            )
        except Exception:
            logger.exception(
                "Scheduled run failed: %s / '%s'", source_name, query
            )

    elapsed = time.monotonic() - start
    logger.info(
        "Finished %s: %d total new records in %.0fs",
        source_name,
        total_inserted,
        elapsed,
    )


def start_scheduler() -> None:
    """Start APScheduler with per-source intervals."""
    scheduler = BlockingScheduler()

    now = datetime.now(tz=timezone.utc)

    # eBay: every 24 hours (sold listings don't change frequently)
    scheduler.add_job(
        _run_source,
        "interval",
        hours=24,
        args=["ebay"],
        id="ebay",
        name="eBay sold listings",
        next_run_time=now,
    )

    # Chrono24: every 12 hours (asking prices update frequently)
    scheduler.add_job(
        _run_source,
        "interval",
        hours=12,
        args=["chrono24"],
        id="chrono24",
        name="Chrono24 asking prices",
        next_run_time=now,
    )

    logger.info("Scheduler started with %d jobs", len(scheduler.get_jobs()))
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped")
