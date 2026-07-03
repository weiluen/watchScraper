"""Reference-centric model: production windows, nicknames, match provenance

Each reference number is the atomic watch. Common names (nicknames) map
many-to-many onto references and are disambiguated by production-year
windows. Price records carry how they were matched and with what confidence.

Revision ID: 005
Revises: 004
Create Date: 2026-07-02
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -- watches: variant attributes + production window + collection name --
    op.add_column("watches", sa.Column("family", sa.String(100)))
    op.add_column("watches", sa.Column("production_start_year", sa.Integer))
    op.add_column("watches", sa.Column("production_end_year", sa.Integer))
    op.add_column("watches", sa.Column("bezel", sa.String(100)))
    op.add_column("watches", sa.Column("bracelet", sa.String(100)))
    op.add_column("watches", sa.Column("has_date", sa.Boolean))
    op.create_index("ix_watches_family", "watches", ["family"])

    # -- nicknames: many references can share one common name ("Batman") --
    op.create_table(
        "watch_nicknames",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "watch_id",
            sa.Integer,
            sa.ForeignKey("watches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("nickname", sa.String(100), nullable=False),
        sa.UniqueConstraint("watch_id", "nickname", name="uq_nickname_per_watch"),
    )
    op.create_index("ix_watch_nicknames_nickname", "watch_nicknames", ["nickname"])

    # -- price_records: match provenance + parsed listing attributes --
    op.add_column("price_records", sa.Column("match_method", sa.String(30)))
    op.add_column("price_records", sa.Column("match_confidence", sa.Float))
    op.add_column("price_records", sa.Column("parsed_year", sa.Integer))
    op.add_column("price_records", sa.Column("parsed_attributes", JSONB))


def downgrade() -> None:
    op.drop_column("price_records", "parsed_attributes")
    op.drop_column("price_records", "parsed_year")
    op.drop_column("price_records", "match_confidence")
    op.drop_column("price_records", "match_method")
    op.drop_index("ix_watch_nicknames_nickname", table_name="watch_nicknames")
    op.drop_table("watch_nicknames")
    op.drop_index("ix_watches_family", table_name="watches")
    op.drop_column("watches", "has_date")
    op.drop_column("watches", "bracelet")
    op.drop_column("watches", "bezel")
    op.drop_column("watches", "production_end_year")
    op.drop_column("watches", "production_start_year")
    op.drop_column("watches", "family")
