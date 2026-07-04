import enum
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from watchscraper.database import Base


class Brand(Base):
    __tablename__ = "brands"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)

    watches: Mapped[list["Watch"]] = relationship(back_populates="brand")


class Watch(Base):
    """One reference number = one watch. The atomic unit of the catalog.

    Values are derived per reference (the variant: dial/material/bezel combo);
    `family` is the common name that groups references (e.g. "Submariner").
    Production years bound which listings can plausibly be this reference.
    """

    __tablename__ = "watches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id"), nullable=False)
    reference_number: Mapped[str] = mapped_column(String(50), nullable=False)
    # NULL = the reference-level watch (single-dial ref, or the mixed parent
    # bucket of a multi-dial ref). Set = a specific dial variant, which is
    # its own watch with its own value ("116508" vs "116508 Green").
    dial_variant: Mapped[str | None] = mapped_column(String(50))
    model_name: Mapped[str] = mapped_column(String(200), nullable=False)
    family: Mapped[str | None] = mapped_column(String(100), index=True)
    case_size_mm: Mapped[float | None] = mapped_column(Float)
    case_material: Mapped[str | None] = mapped_column(String(100))
    dial_color: Mapped[str | None] = mapped_column(String(100))
    bezel: Mapped[str | None] = mapped_column(String(100))
    bracelet: Mapped[str | None] = mapped_column(String(100))
    has_date: Mapped[bool | None] = mapped_column(Boolean)
    movement: Mapped[str | None] = mapped_column(String(100))
    production_start_year: Mapped[int | None] = mapped_column(Integer)
    production_end_year: Mapped[int | None] = mapped_column(Integer)  # None = current
    retail_price_usd: Mapped[int | None] = mapped_column(BigInteger)

    # Full WatchCharts-style spec dimensions
    style: Mapped[str | None] = mapped_column(String(30))
    complications: Mapped[str | None] = mapped_column(String(300))  # comma-joined
    features: Mapped[str | None] = mapped_column(String(500))       # comma-joined
    movement_type: Mapped[str | None] = mapped_column(String(30))
    frequency_bph: Mapped[int | None] = mapped_column(Integer)
    jewels: Mapped[int | None] = mapped_column(Integer)
    power_reserve_hours: Mapped[int | None] = mapped_column(Integer)
    crystal: Mapped[str | None] = mapped_column(String(40))
    dial_numerals: Mapped[str | None] = mapped_column(String(40))
    lug_width_mm: Mapped[float | None] = mapped_column(Float)
    water_resistance_m: Mapped[int | None] = mapped_column(Integer)
    case_thickness_mm: Mapped[float | None] = mapped_column(Float)

    brand: Mapped["Brand"] = relationship(back_populates="watches")
    aliases: Mapped[list["WatchAlias"]] = relationship(back_populates="watch")
    nicknames: Mapped[list["WatchNickname"]] = relationship(back_populates="watch")
    price_records: Mapped[list["PriceRecord"]] = relationship(back_populates="watch")


class WatchAlias(Base):
    """Alternate reference spellings that map 1:1 to a watch (e.g. long-form
    AP refs). For common names shared by several references, use
    WatchNickname."""

    __tablename__ = "watch_aliases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    watch_id: Mapped[int] = mapped_column(ForeignKey("watches.id"), nullable=False)
    alias: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)

    watch: Mapped["Watch"] = relationship(back_populates="aliases")


class ActiveListing(Base):
    """A currently-or-formerly active asking listing, tracked over time.

    Each scrape refreshes last_seen for listings still present. When a
    listing stops appearing it is delisted (presumed sold); days_on_market =
    delisted_at - first_seen. Powers the median-days-on-market and listing
    liquidity metrics.
    """

    __tablename__ = "active_listings"
    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="uq_active_listing"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), nullable=False)
    external_id: Mapped[str] = mapped_column(String(200), nullable=False)
    watch_id: Mapped[int | None] = mapped_column(ForeignKey("watches.id"))
    family: Mapped[str | None] = mapped_column(String(100))
    ask_price_usd: Mapped[int | None] = mapped_column(BigInteger)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    delisted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    days_on_market: Mapped[int | None] = mapped_column(Integer)


class WatchNickname(Base):
    """Community common names ("Batman", "Hulk", "Pepsi").

    Deliberately NOT unique per nickname: "Batman" is both 116710BLNR
    (2013-2019) and 126710BLNR (2019+) — the matcher disambiguates candidates
    by production-year windows and listing attributes.
    """

    __tablename__ = "watch_nicknames"
    __table_args__ = (
        UniqueConstraint("watch_id", "nickname", name="uq_nickname_per_watch"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    watch_id: Mapped[int] = mapped_column(ForeignKey("watches.id"), nullable=False)
    nickname: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    watch: Mapped["Watch"] = relationship(back_populates="nicknames")


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    scraper_type: Mapped[str] = mapped_column(String(50), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    price_records: Mapped[list["PriceRecord"]] = relationship(back_populates="source")
    scrape_runs: Mapped[list["ScrapeRun"]] = relationship(back_populates="source")


class PriceType(enum.Enum):
    ASKING = "asking"
    SOLD = "sold"
    ESTIMATED = "estimated"


class Condition(enum.Enum):
    NEW = "new"
    UNWORN = "unworn"
    VERY_GOOD = "very_good"
    GOOD = "good"
    FAIR = "fair"
    UNKNOWN = "unknown"


class PriceRecord(Base):
    __tablename__ = "price_records"
    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="uq_price_source_ext"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    watch_id: Mapped[int | None] = mapped_column(ForeignKey("watches.id"))
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), nullable=False)
    price_usd: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # Stored as enum VALUES ("asking"), matching the raw-SQL analysis layer
    price_type: Mapped[PriceType] = mapped_column(
        Enum(
            PriceType,
            native_enum=False,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
    )
    condition: Mapped[Condition] = mapped_column(
        Enum(
            Condition,
            native_enum=False,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=Condition.UNKNOWN,
    )
    has_box: Mapped[bool | None] = mapped_column(Boolean)
    has_papers: Mapped[bool | None] = mapped_column(Boolean)
    listing_url: Mapped[str | None] = mapped_column(Text)
    external_id: Mapped[str] = mapped_column(String(200), nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    reference_parsed: Mapped[str | None] = mapped_column(String(50))
    match_method: Mapped[str | None] = mapped_column(String(30))
    match_confidence: Mapped[float | None] = mapped_column(Float)
    parsed_year: Mapped[int | None] = mapped_column(Integer)
    parsed_attributes: Mapped[dict | None] = mapped_column(JSONB)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    raw_data: Mapped[dict | None] = mapped_column(JSONB)

    watch: Mapped["Watch | None"] = relationship(back_populates="price_records")
    source: Mapped["Source"] = relationship(back_populates="price_records")


class PortfolioHolding(Base):
    __tablename__ = "portfolio_holdings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nickname: Mapped[str | None] = mapped_column(String(200))
    brand: Mapped[str] = mapped_column(String(100), nullable=False)
    family: Mapped[str] = mapped_column(String(100), nullable=False)
    reference_number: Mapped[str | None] = mapped_column(String(50))
    dial_variant: Mapped[str | None] = mapped_column(String(50))
    purchase_price_usd: Mapped[float | None] = mapped_column(Float)
    purchase_date: Mapped[date | None] = mapped_column(Date)
    condition: Mapped[str | None] = mapped_column(String(20))
    contents: Mapped[str | None] = mapped_column(String(20))
    is_wishlist: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class PriceAlert(Base):
    """A user's price alert for a watch: notify when value crosses threshold."""

    __tablename__ = "price_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    brand: Mapped[str] = mapped_column(String(100), nullable=False)
    family: Mapped[str] = mapped_column(String(100), nullable=False)
    reference_number: Mapped[str | None] = mapped_column(String(50))
    dial_variant: Mapped[str | None] = mapped_column(String(50))
    threshold_usd: Mapped[float] = mapped_column(Float, nullable=False)
    direction: Mapped[str] = mapped_column(String(5), nullable=False)
    email: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ScrapeRunStatus(enum.Enum):
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class ScrapeRun(Base):
    __tablename__ = "scrape_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), nullable=False)
    status: Mapped[ScrapeRunStatus] = mapped_column(
        Enum(ScrapeRunStatus, native_enum=False), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    records_scraped: Mapped[int] = mapped_column(Integer, default=0)
    records_inserted: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)

    source: Mapped["Source"] = relationship(back_populates="scrape_runs")
