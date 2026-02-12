"""Initial schema — brands, watches, aliases, sources, price_records, scrape_runs

Revision ID: 001
Revises: None
Create Date: 2026-02-08
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "brands",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
    )

    op.create_table(
        "watches",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("brand_id", sa.Integer, sa.ForeignKey("brands.id"), nullable=False),
        sa.Column("reference_number", sa.String(50), nullable=False),
        sa.Column("model_name", sa.String(200), nullable=False),
        sa.Column("case_size_mm", sa.Float),
        sa.Column("case_material", sa.String(100)),
        sa.Column("dial_color", sa.String(100)),
        sa.Column("movement", sa.String(100)),
        sa.Column("retail_price_usd", sa.BigInteger),
        sa.UniqueConstraint("brand_id", "reference_number", name="uq_watch_brand_ref"),
    )

    op.create_table(
        "watch_aliases",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "watch_id", sa.Integer, sa.ForeignKey("watches.id"), nullable=False
        ),
        sa.Column("alias", sa.String(100), nullable=False, unique=True),
    )

    op.create_table(
        "sources",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("base_url", sa.String(500), nullable=False),
        sa.Column("scraper_type", sa.String(50), nullable=False),
        sa.Column("is_active", sa.Boolean, default=True),
    )

    op.create_table(
        "price_records",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("watch_id", sa.Integer, sa.ForeignKey("watches.id")),
        sa.Column(
            "source_id", sa.Integer, sa.ForeignKey("sources.id"), nullable=False
        ),
        sa.Column("price_usd", sa.BigInteger, nullable=False),
        sa.Column("price_type", sa.String(20), nullable=False),
        sa.Column("condition", sa.String(20), default="unknown"),
        sa.Column("has_box", sa.Boolean),
        sa.Column("has_papers", sa.Boolean),
        sa.Column("listing_url", sa.Text),
        sa.Column("external_id", sa.String(200), nullable=False),
        sa.Column("title", sa.Text),
        sa.Column("reference_parsed", sa.String(50)),
        sa.Column("observed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "scraped_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("raw_data", JSONB),
        sa.UniqueConstraint("source_id", "external_id", name="uq_price_source_ext"),
    )

    op.create_index(
        "ix_price_records_watch_id", "price_records", ["watch_id"]
    )
    op.create_index(
        "ix_price_records_observed_at", "price_records", ["observed_at"]
    )

    op.create_table(
        "scrape_runs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "source_id", sa.Integer, sa.ForeignKey("sources.id"), nullable=False
        ),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("records_scraped", sa.Integer, default=0),
        sa.Column("records_inserted", sa.Integer, default=0),
        sa.Column("error_message", sa.Text),
    )


def downgrade() -> None:
    op.drop_table("scrape_runs")
    op.drop_index("ix_price_records_observed_at", table_name="price_records")
    op.drop_index("ix_price_records_watch_id", table_name="price_records")
    op.drop_table("price_records")
    op.drop_table("sources")
    op.drop_table("watch_aliases")
    op.drop_table("watches")
    op.drop_table("brands")
