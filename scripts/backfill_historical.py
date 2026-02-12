"""Backfill historical price data from WatchCharts and eBay."""

import logging

from sqlalchemy import select

from watchscraper.database import get_session
from watchscraper.models import Watch
from watchscraper.pipeline import run_pipeline
from watchscraper.scrapers.ebay import EbayScraper
from watchscraper.scrapers.watchcharts import WatchChartsScraper

logger = logging.getLogger(__name__)

# Full history (price_full, 10 credits) — high-end brands with thin eBay/Chrono24 data
BRANDS_FULL = {
    "Rolex",
    "Patek Philippe",
    "Audemars Piguet",
    "A. Lange & Söhne",
    "Vacheron Constantin",
}

# 1-year history (price_1y, 3 credits) — brands with better eBay/Chrono24 coverage
BRANDS_1Y = {
    "Omega",
    "IWC",
    "Cartier",
    "Jaeger-LeCoultre",
}

# Credit costs: search=1, price_1y=3, price_full=10
CREDIT_SEARCH = 1
CREDIT_1Y = 3
CREDIT_FULL = 10


def run_backfill(
    source: str = "watchcharts",
    dry_run: bool = False,
    test: bool = False,
    brands: list[str] | None = None,
) -> None:
    session = get_session()
    try:
        watches = session.execute(select(Watch)).scalars().all()
        logger.info("Backfilling %d watches from %s", len(watches), source)

        if source == "watchcharts":
            _backfill_watchcharts(watches, dry_run=dry_run, test=test, brands=brands)
        elif source == "ebay":
            _backfill_ebay(watches)
        else:
            logger.error("Unknown backfill source: %s", source)
    finally:
        session.close()


def _backfill_watchcharts(
    watches: list[Watch],
    dry_run: bool = False,
    test: bool = False,
    brands: list[str] | None = None,
) -> None:
    scraper = WatchChartsScraper()
    total_records = 0
    total_credits = 0

    # Filter to eligible watches (must have brand + reference, brand in our tier lists)
    eligible = []
    for watch in watches:
        brand_name = watch.brand.name if watch.brand else None
        ref = watch.reference_number
        if not brand_name or not ref:
            continue
        if brand_name not in BRANDS_FULL and brand_name not in BRANDS_1Y:
            continue
        if brands and brand_name not in brands:
            continue
        eligible.append(watch)

    if dry_run:
        print(f"\n{'='*70}")
        print("DRY RUN — WatchCharts Historical Backfill Credit Estimate")
        print(f"{'='*70}\n")
        dry_credits = 0
        for watch in eligible:
            brand_name = watch.brand.name
            ref = watch.reference_number
            if brand_name in BRANDS_FULL:
                tier = "full"
                cost = CREDIT_SEARCH + CREDIT_FULL
            else:
                tier = "1y"
                cost = CREDIT_SEARCH + CREDIT_1Y
            dry_credits += cost
            print(f"  {brand_name:<25s} {ref:<20s} tier={tier}  credits={cost}")
        print(f"\n{'─'*70}")
        print(f"  Total watches: {len(eligible)}")
        print(f"  Estimated credits: {dry_credits}")
        print(f"  Estimated API calls: {len(eligible) * 2}")
        print(f"  Estimated runtime: ~{len(eligible) * 2 * 1.1 / 60:.1f} minutes")
        return

    for i, watch in enumerate(eligible):
        brand_name = watch.brand.name
        ref = watch.reference_number

        if brand_name in BRANDS_FULL:
            days = 9999  # triggers price_full path
            history_credits = CREDIT_FULL
        else:
            days = 365  # triggers price_1y path
            history_credits = CREDIT_1Y

        try:
            # Step 1: Search for UUID (1 credit)
            wc_brand = scraper.BRAND_MAP.get(
                brand_name.lower().replace(" ", "-"),
                scraper.BRAND_MAP.get(brand_name.lower(), brand_name),
            )
            uuid = scraper._search(wc_brand, ref)
            total_credits += CREDIT_SEARCH
            if not uuid:
                logger.info("Backfill skip — no WatchCharts match for %s %s", brand_name, ref)
                if test:
                    print(f"TEST: No UUID found for {brand_name} {ref}. Credits used: {total_credits}")
                    return
                continue

            # Step 2: Pull history
            listings = scraper.get_historical(uuid, days=days)
            total_credits += history_credits
            if not listings:
                logger.info("Backfill skip — no history for %s %s (uuid=%s)", brand_name, ref, uuid)
                if test:
                    print(f"TEST: No history for {brand_name} {ref}. Credits used: {total_credits}")
                    return
                continue

            # Step 3: Dedup and insert
            from watchscraper.dedup import get_existing_external_ids
            from watchscraper.models import PriceRecord, Source

            session = get_session()
            src = session.execute(
                select(Source).where(Source.name == "watchcharts")
            ).scalar_one_or_none()
            if not src:
                logger.error("WatchCharts source not found — run seed first")
                return

            ext_ids = [l.external_id for l in listings]
            existing = get_existing_external_ids(session, "watchcharts", ext_ids)
            new_listings = [l for l in listings if l.external_id not in existing]

            for listing in new_listings:
                record = PriceRecord(
                    watch_id=watch.id,
                    source_id=src.id,
                    price_usd=listing.price_usd,
                    price_type=listing.price_type,
                    condition=listing.condition,
                    listing_url=listing.listing_url,
                    external_id=listing.external_id,
                    title=listing.title,
                    reference_parsed=listing.reference_parsed or ref,
                    observed_at=listing.observed_at,
                    raw_data=listing.raw_data,
                )
                session.add(record)
                total_records += 1

            session.commit()
            session.close()
            logger.info(
                "Backfill %s %s: %d new records (uuid=%s, credits_so_far=%d)",
                brand_name, ref, len(new_listings), uuid, total_credits,
            )

            if test:
                print(f"TEST: {brand_name} {ref} — {len(new_listings)} new records, "
                      f"{len(listings)} data points. Credits used: {total_credits}")
                return

        except Exception:
            logger.exception("Backfill failed for %s %s", brand_name, ref)

    logger.info(
        "WatchCharts backfill complete: %d total records, %d credits used",
        total_records, total_credits,
    )


def _backfill_ebay(watches: list[Watch]) -> None:
    scraper = EbayScraper()
    total = 0
    for watch in watches:
        query = f"{watch.brand.name} {watch.model_name} {watch.reference_number}"
        try:
            count = run_pipeline(scraper, query, max_pages=5)
            total += count
            logger.info(
                "eBay backfill %s: %d records",
                watch.reference_number,
                count,
            )
        except Exception:
            logger.exception(
                "eBay backfill failed for %s", watch.reference_number
            )

    logger.info("eBay backfill complete: %d total records", total)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_backfill()
