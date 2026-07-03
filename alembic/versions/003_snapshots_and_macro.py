"""Add price_snapshots and macro_series tables for time-series modeling

Revision ID: 003
Revises: 002
Create Date: 2026-07-01
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "price_snapshots",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("snapshot_date", sa.Date, nullable=False),
        sa.Column("brand", sa.String(100), nullable=False),
        sa.Column("family", sa.String(100), nullable=False),
        sa.Column("price_type", sa.String(20), nullable=False),
        sa.Column("n", sa.Integer, nullable=False),
        sa.Column("median_usd", sa.Float, nullable=False),
        sa.Column("p25_usd", sa.Float),
        sa.Column("p75_usd", sa.Float),
        sa.Column("mean_usd", sa.Float),
        sa.Column("std_usd", sa.Float),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "snapshot_date",
            "brand",
            "family",
            "price_type",
            name="uq_snapshot_week_family_type",
        ),
    )
    op.create_index(
        "ix_price_snapshots_family_date",
        "price_snapshots",
        ["family", "snapshot_date"],
    )

    op.create_table(
        "macro_series",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("series_id", sa.String(50), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("value", sa.Float, nullable=False),
        sa.UniqueConstraint("series_id", "date", name="uq_macro_series_date"),
    )
    op.create_index("ix_macro_series_id_date", "macro_series", ["series_id", "date"])


def downgrade() -> None:
    op.drop_index("ix_macro_series_id_date", table_name="macro_series")
    op.drop_table("macro_series")
    op.drop_index("ix_price_snapshots_family_date", table_name="price_snapshots")
    op.drop_table("price_snapshots")
