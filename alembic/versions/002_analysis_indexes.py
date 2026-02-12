"""Add composite indexes for analysis queries

Revision ID: 002
Revises: 001
Create Date: 2026-02-09
"""
from typing import Sequence, Union

from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Efficient per-watch time-series queries (value retention over time)
    op.create_index(
        "ix_price_records_watch_observed",
        "price_records",
        ["watch_id", "observed_at"],
    )
    # Per-watch-per-source queries (eBay sold vs Chrono24 asking)
    op.create_index(
        "ix_price_records_watch_source_observed",
        "price_records",
        ["watch_id", "source_id", "observed_at"],
    )
    # Reference lookups for backfill
    op.create_index(
        "ix_price_records_reference_parsed",
        "price_records",
        ["reference_parsed"],
    )


def downgrade() -> None:
    op.drop_index("ix_price_records_reference_parsed", table_name="price_records")
    op.drop_index("ix_price_records_watch_source_observed", table_name="price_records")
    op.drop_index("ix_price_records_watch_observed", table_name="price_records")
