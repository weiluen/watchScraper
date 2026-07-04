"""Full WatchCharts-style specs on watches + active_listings for days-on-market

Adds the complete spec dimension set (Style, Complications, Features,
movement details, remaining case specs) so every watch carries the same
granular categorization WatchCharts uses. Adds active_listings to track a
listing's appearance→disappearance for the median-days-on-market and
liquidity metrics.

Revision ID: 008
Revises: 007
Create Date: 2026-07-04
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SPEC_COLUMNS = [
    ("style", sa.String(30)),
    ("complications", sa.String(300)),  # comma-joined
    ("features", sa.String(500)),       # comma-joined
    ("movement_type", sa.String(30)),
    ("frequency_bph", sa.Integer),
    ("jewels", sa.Integer),
    ("power_reserve_hours", sa.Integer),
    ("crystal", sa.String(40)),
    ("dial_numerals", sa.String(40)),
    ("lug_width_mm", sa.Float),
    ("water_resistance_m", sa.Integer),
    ("case_thickness_mm", sa.Float),
]


def upgrade() -> None:
    for name, col_type in SPEC_COLUMNS:
        op.add_column("watches", sa.Column(name, col_type))

    op.create_table(
        "active_listings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("source_id", sa.Integer, sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("external_id", sa.String(200), nullable=False),
        sa.Column("watch_id", sa.Integer, sa.ForeignKey("watches.id")),
        sa.Column("family", sa.String(100)),
        sa.Column("ask_price_usd", sa.BigInteger),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delisted_at", sa.DateTime(timezone=True)),
        sa.Column("days_on_market", sa.Integer),
        sa.UniqueConstraint("source_id", "external_id", name="uq_active_listing"),
    )
    op.create_index("ix_active_listings_watch", "active_listings", ["watch_id"])
    op.create_index("ix_active_listings_family", "active_listings", ["family"])


def downgrade() -> None:
    op.drop_index("ix_active_listings_family", table_name="active_listings")
    op.drop_index("ix_active_listings_watch", table_name="active_listings")
    op.drop_table("active_listings")
    for name, _ in reversed(SPEC_COLUMNS):
        op.drop_column("watches", name)
