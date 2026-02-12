import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
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
    __tablename__ = "watches"
    __table_args__ = (
        UniqueConstraint("brand_id", "reference_number", name="uq_watch_brand_ref"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id"), nullable=False)
    reference_number: Mapped[str] = mapped_column(String(50), nullable=False)
    model_name: Mapped[str] = mapped_column(String(200), nullable=False)
    case_size_mm: Mapped[float | None] = mapped_column(Float)
    case_material: Mapped[str | None] = mapped_column(String(100))
    dial_color: Mapped[str | None] = mapped_column(String(100))
    movement: Mapped[str | None] = mapped_column(String(100))
    retail_price_usd: Mapped[int | None] = mapped_column(BigInteger)

    brand: Mapped["Brand"] = relationship(back_populates="watches")
    aliases: Mapped[list["WatchAlias"]] = relationship(back_populates="watch")
    price_records: Mapped[list["PriceRecord"]] = relationship(back_populates="watch")


class WatchAlias(Base):
    __tablename__ = "watch_aliases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    watch_id: Mapped[int] = mapped_column(ForeignKey("watches.id"), nullable=False)
    alias: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)

    watch: Mapped["Watch"] = relationship(back_populates="aliases")


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
    price_type: Mapped[PriceType] = mapped_column(
        Enum(PriceType, native_enum=False), nullable=False
    )
    condition: Mapped[Condition] = mapped_column(
        Enum(Condition, native_enum=False), default=Condition.UNKNOWN
    )
    has_box: Mapped[bool | None] = mapped_column(Boolean)
    has_papers: Mapped[bool | None] = mapped_column(Boolean)
    listing_url: Mapped[str | None] = mapped_column(Text)
    external_id: Mapped[str] = mapped_column(String(200), nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    reference_parsed: Mapped[str | None] = mapped_column(String(50))
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    raw_data: Mapped[dict | None] = mapped_column(JSONB)

    watch: Mapped["Watch | None"] = relationship(back_populates="price_records")
    source: Mapped["Source"] = relationship(back_populates="price_records")


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
