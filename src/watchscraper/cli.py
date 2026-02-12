import logging
import shutil
import subprocess
import sys
from pathlib import Path

import click

from watchscraper.config import settings

PLIST_NAME = "com.watchscraper.scheduler.plist"
PROJECT_DIR = Path(__file__).resolve().parent.parent.parent  # watchScraper/
PLIST_SRC = PROJECT_DIR / PLIST_NAME
LAUNCH_AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"
PLIST_DST = LAUNCH_AGENTS_DIR / PLIST_NAME
LOG_DIR = Path.home() / "Library" / "Logs" / "watchscraper"


def _setup_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stderr,
    )


@click.group()
def cli() -> None:
    """watchScraper — luxury watch price tracker."""
    _setup_logging()


@cli.command()
@click.option(
    "--source",
    type=click.Choice(["ebay", "chrono24", "watchcharts", "hodinkee"]),
    required=True,
    help="Source to scrape.",
)
@click.option(
    "--brand",
    type=str,
    default=None,
    help="Brand name to filter queries (e.g. 'Rolex').",
)
@click.option(
    "--query",
    type=str,
    default=None,
    help="Custom search query (overrides brand-based queries).",
)
@click.option("--max-pages", type=int, default=3, help="Max pages per query.")
def scrape(source: str, brand: str | None, query: str | None, max_pages: int) -> None:
    """Run a scraper for a specific source."""
    from watchscraper.pipeline import run_pipeline
    from watchscraper.scrapers.chrono24 import Chrono24Scraper
    from watchscraper.scrapers.ebay import EbayScraper
    from watchscraper.scrapers.hodinkee import HodinkeeScraper
    from watchscraper.scrapers.watchcharts import WatchChartsScraper

    scrapers = {
        "ebay": EbayScraper,
        "chrono24": Chrono24Scraper,
        "watchcharts": WatchChartsScraper,
        "hodinkee": HodinkeeScraper,
    }

    scraper = scrapers[source]()
    queries = _build_queries(brand, query)

    total = 0
    for q in queries:
        click.echo(f"Scraping {source}: '{q}'...")
        try:
            count = run_pipeline(scraper, q, max_pages=max_pages)
            total += count
            click.echo(f"  → {count} new records")
        except Exception as e:
            click.echo(f"  ✗ Failed: {e}", err=True)

    click.echo(f"\nDone. {total} total new records from {source}.")


@cli.command()
def seed() -> None:
    """Seed the database with reference watches and sources."""
    from scripts.seed_watches import run_seed

    run_seed()
    click.echo("Seed complete.")


@cli.command()
def schedule() -> None:
    """Start the APScheduler daemon for periodic scraping."""
    from watchscraper.scheduler import start_scheduler

    click.echo("Starting scheduler (Ctrl+C to stop)...")
    start_scheduler()


@cli.command()
@click.option(
    "--source",
    type=click.Choice(["watchcharts"]),
    default="watchcharts",
    help="Source for backfill.",
)
@click.option("--dry-run", is_flag=True, help="Show watch list + credit estimate, don't call API.")
@click.option("--test", is_flag=True, help="Backfill 1 watch only, print results.")
@click.option("--brands", type=str, default=None, help="Comma-separated brand filter (e.g. 'Rolex,Omega').")
def backfill(source: str, dry_run: bool, test: bool, brands: str | None) -> None:
    """Backfill historical price data."""
    from scripts.backfill_historical import run_backfill

    brands_list = [b.strip() for b in brands.split(",")] if brands else None

    if dry_run:
        click.echo(f"Dry run — estimating credits for {source}...")
    elif test:
        click.echo(f"Test mode — backfilling 1 watch from {source}...")
    else:
        click.echo(f"Backfilling from {source}...")

    run_backfill(source=source, dry_run=dry_run, test=test, brands=brands_list)
    click.echo("Backfill complete.")


@cli.command()
def stats() -> None:
    """Show database statistics."""
    from sqlalchemy import func, select

    from watchscraper.database import get_session
    from watchscraper.models import Brand, PriceRecord, ScrapeRun, Source, Watch

    session = get_session()
    try:
        brands = session.execute(select(func.count(Brand.id))).scalar() or 0
        watches = session.execute(select(func.count(Watch.id))).scalar() or 0
        records = session.execute(select(func.count(PriceRecord.id))).scalar() or 0
        runs = session.execute(select(func.count(ScrapeRun.id))).scalar() or 0

        click.echo(f"Brands:        {brands}")
        click.echo(f"Watches:       {watches}")
        click.echo(f"Price records: {records}")
        click.echo(f"Scrape runs:   {runs}")

        # Per-source breakdown
        stmt = (
            select(Source.name, func.count(PriceRecord.id))
            .join(PriceRecord, PriceRecord.source_id == Source.id)
            .group_by(Source.name)
        )
        rows = session.execute(stmt).all()
        if rows:
            click.echo("\nRecords by source:")
            for name, count in rows:
                click.echo(f"  {name}: {count}")
    finally:
        session.close()


@cli.command()
def install() -> None:
    """Install the scheduler as a macOS launchd background service."""
    if not PLIST_SRC.exists():
        click.echo(f"Plist not found at {PLIST_SRC}", err=True)
        raise SystemExit(1)

    # Create log directory
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Copy plist to ~/Library/LaunchAgents/
    LAUNCH_AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(PLIST_SRC, PLIST_DST)
    click.echo(f"Installed plist to {PLIST_DST}")

    # Load the service
    subprocess.run(["launchctl", "load", str(PLIST_DST)], check=True)
    click.echo("Scheduler service loaded. It will run on login and stay alive.")
    click.echo(f"Logs: {LOG_DIR / 'scheduler.log'}")
    click.echo("Check status: launchctl list | grep watchscraper")


@cli.command()
def uninstall() -> None:
    """Uninstall the scheduler launchd background service."""
    if not PLIST_DST.exists():
        click.echo("Scheduler service is not installed.")
        return

    subprocess.run(["launchctl", "unload", str(PLIST_DST)], check=False)
    PLIST_DST.unlink()
    click.echo("Scheduler service unloaded and removed.")


@cli.command()
@click.option("--output", "-o", type=click.Path(), default="data/prices.csv", help="Output CSV path.")
def export(output: str) -> None:
    """Export analysis-ready CSV of all linked price records."""
    from sqlalchemy import text

    import pandas as pd

    from watchscraper.database import engine

    query = text("""
        SELECT
            b.name AS brand,
            w.reference_number AS ref,
            w.model_name AS model,
            w.retail_price_usd / 100.0 AS retail_price,
            w.case_material AS material,
            pr.price_usd / 100.0 AS market_price,
            pr.price_type,
            pr.condition,
            s.name AS source,
            pr.observed_at,
            pr.scraped_at
        FROM price_records pr
        JOIN watches w ON pr.watch_id = w.id
        JOIN brands b ON w.brand_id = b.id
        JOIN sources s ON pr.source_id = s.id
        WHERE pr.watch_id IS NOT NULL
        ORDER BY pr.scraped_at
    """)

    df = pd.read_sql(query, engine)
    outpath = Path(output)
    outpath.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(outpath, index=False)
    click.echo(f"Exported {len(df)} records to {outpath}")


@cli.command()
@click.option("--top", "-n", type=int, default=15, help="Number of top/bottom models to show.")
@click.option("--months", "-m", type=int, default=6, help="Lookback window in months for trend calculation.")
def analyze(top: int, months: int) -> None:
    """Analyze grey market price trends and value stability."""
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import text

    import pandas as pd

    from watchscraper.database import engine

    # Load eBay sold data (has actual sale dates for trend analysis)
    query = text("""
        SELECT
            b.name AS brand,
            w.reference_number AS ref,
            w.model_name AS model,
            w.retail_price_usd / 100.0 AS retail_price,
            pr.price_usd / 100.0 AS market_price,
            pr.price_type,
            pr.observed_at,
            pr.scraped_at,
            s.name AS source
        FROM price_records pr
        JOIN watches w ON pr.watch_id = w.id
        JOIN brands b ON w.brand_id = b.id
        JOIN sources s ON pr.source_id = s.id
        WHERE pr.watch_id IS NOT NULL
    """)

    df = pd.read_sql(query, engine)
    if df.empty:
        click.echo("No linked records found. Run 'watchscraper seed' and scrape first.")
        return

    # Split by source type
    sold = df[df["price_type"] == "sold"].copy()
    asking = df[df["price_type"] == "asking"].copy()

    # ── Current Grey Market Prices by Brand ──
    click.echo("=" * 75)
    click.echo("GREY MARKET PRICES BY BRAND (median sold price)")
    click.echo("=" * 75)

    brand_prices = (
        sold.groupby("brand")
        .agg(
            median_sold=("market_price", "median"),
            sold_count=("market_price", "count"),
            models=("ref", "nunique"),
        )
        .sort_values("median_sold", ascending=False)
    )
    for brand, row in brand_prices.iterrows():
        click.echo(
            f"  {brand:<25s} ${row['median_sold']:>10,.0f}  "
            f"({int(row['sold_count'])} sales, {int(row['models'])} models)"
        )

    # ── Price Trend: compare recent vs older sold prices ──
    cutoff = datetime.now(timezone.utc) - timedelta(days=months * 30)
    sold["observed_at"] = pd.to_datetime(sold["observed_at"], utc=True)
    recent = sold[sold["observed_at"] >= cutoff]
    older = sold[sold["observed_at"] < cutoff]

    if not older.empty and not recent.empty:
        recent_med = recent.groupby("ref")["market_price"].median().rename("recent_median")
        older_med = older.groupby("ref")["market_price"].median().rename("older_median")
        trend = pd.concat([recent_med, older_med], axis=1).dropna()
        trend["change_pct"] = ((trend["recent_median"] - trend["older_median"]) / trend["older_median"]) * 100

        # Add brand/model info
        ref_info = sold.drop_duplicates("ref")[["ref", "brand", "model"]].set_index("ref")
        ref_counts = recent.groupby("ref").size().rename("recent_count")
        trend = trend.join(ref_info).join(ref_counts)
        trend = trend[trend["recent_count"] >= 3].sort_values("change_pct", ascending=False)

        if not trend.empty:
            click.echo(f"\n{'=' * 75}")
            click.echo(f"PRICE TRENDS (last {months}mo vs prior — 3+ recent sales)")
            click.echo("=" * 75)

            appreciating = trend[trend["change_pct"] > 0]
            depreciating = trend[trend["change_pct"] <= 0]

            if not appreciating.empty:
                click.echo(f"\n  APPRECIATING ({len(appreciating)} models):")
                for ref, row in appreciating.head(top).iterrows():
                    click.echo(
                        f"    {row['brand']:<20s} {ref:<15s} +{row['change_pct']:5.1f}%  "
                        f"${row['older_median']:>9,.0f} -> ${row['recent_median']:>9,.0f}"
                    )

            if not depreciating.empty:
                click.echo(f"\n  DEPRECIATING ({len(depreciating)} models):")
                for ref, row in depreciating.tail(top).iterrows():
                    click.echo(
                        f"    {row['brand']:<20s} {ref:<15s} {row['change_pct']:5.1f}%  "
                        f"${row['older_median']:>9,.0f} -> ${row['recent_median']:>9,.0f}"
                    )

    # ── Price Stability (coefficient of variation) ──
    stability = (
        sold.groupby(["brand", "ref", "model"])
        .agg(
            median_price=("market_price", "median"),
            std_price=("market_price", "std"),
            count=("market_price", "count"),
        )
        .reset_index()
        .query("count >= 5")
    )
    stability["cv"] = (stability["std_price"] / stability["median_price"]) * 100

    click.echo(f"\n{'=' * 75}")
    click.echo(f"MOST STABLE PRICES (lowest coefficient of variation, 5+ sales)")
    click.echo("=" * 75)
    stable_sorted = stability.sort_values("cv")
    for _, row in stable_sorted.head(top).iterrows():
        click.echo(
            f"  {row['brand']:<20s} {row['ref']:<15s} CV={row['cv']:5.1f}%  "
            f"${row['median_price']:>10,.0f} median  ({int(row['count'])} sales)"
        )

    # ── Asking vs Sold Spread ──
    if not asking.empty and not sold.empty:
        ask_med = asking.groupby("ref")["market_price"].median().rename("asking_median")
        sold_med = sold.groupby("ref")["market_price"].median().rename("sold_median")
        spread = pd.concat([ask_med, sold_med], axis=1).dropna()
        spread["spread_pct"] = ((spread["asking_median"] - spread["sold_median"]) / spread["sold_median"]) * 100
        spread = spread.join(ref_info if "ref_info" in dir() else sold.drop_duplicates("ref")[["ref", "brand", "model"]].set_index("ref"))

        click.echo(f"\n{'=' * 75}")
        click.echo("ASKING vs SOLD SPREAD (Chrono24 asking / eBay sold)")
        click.echo("=" * 75)
        spread_sorted = spread.sort_values("spread_pct", ascending=False)
        for ref, row in spread_sorted.head(top).iterrows():
            click.echo(
                f"  {row.get('brand', '?'):<20s} {ref:<15s} +{row['spread_pct']:5.1f}%  "
                f"ask ${row['asking_median']:>9,.0f} / sold ${row['sold_median']:>9,.0f}"
            )

    click.echo(f"\nTotal: {len(sold)} sold + {len(asking)} asking records across {df['ref'].nunique()} models")


def _build_queries(brand: str | None, custom_query: str | None) -> list[str]:
    """Build search queries from brand or custom query."""
    if custom_query:
        return [custom_query]

    # Default queries grouped by brand
    brand_queries: dict[str, list[str]] = {
        "rolex": [
            "Rolex Submariner",
            "Rolex Daytona",
            "Rolex GMT-Master II",
            "Rolex Datejust 41",
            "Rolex Explorer",
            "Rolex Sky-Dweller",
        ],
        "ap": [
            "Audemars Piguet Royal Oak",
            "Audemars Piguet Royal Oak Offshore",
        ],
        "patek": [
            "Patek Philippe Nautilus",
            "Patek Philippe Aquanaut",
            "Patek Philippe Calatrava",
        ],
        "omega": [
            "Omega Speedmaster",
            "Omega Seamaster 300M",
            "Omega Seamaster Aqua Terra",
            "Omega Seamaster Planet Ocean",
        ],
        "vacheron": [
            "Vacheron Constantin Overseas",
            "Vacheron Constantin Patrimony",
            "Vacheron Constantin Traditionnelle",
            "Vacheron Constantin Fiftysix",
        ],
        "iwc": [
            "IWC Portugieser",
            "IWC Big Pilot",
            "IWC Pilot Mark",
            "IWC Aquatimer",
        ],
        "jaeger": [
            "Jaeger-LeCoultre Reverso",
            "Jaeger-LeCoultre Master Ultra Thin",
            "Jaeger-LeCoultre Polaris",
        ],
        "lange": [
            "A. Lange Sohne Lange 1",
            "A. Lange Sohne Saxonia",
            "A. Lange Sohne Datograph",
            "A. Lange Sohne 1815",
        ],
        "cartier": [
            "Cartier Santos",
            "Cartier Tank",
            "Cartier Ballon Bleu",
            "Cartier Pasha",
        ],
    }

    if brand:
        key = brand.lower().replace(" ", "")
        # Allow partial matches: "rolex" → rolex, "audemars" → ap
        for k, queries in brand_queries.items():
            if key.startswith(k) or k.startswith(key):
                return queries
        # Fallback: use brand as query
        return [brand]

    # All brands
    all_queries: list[str] = []
    for queries in brand_queries.values():
        all_queries.extend(queries)
    return all_queries


if __name__ == "__main__":
    cli()
