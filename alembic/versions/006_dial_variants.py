"""Dial variants: a reference with multiple dials is multiple watches

The dial (and material combo it implies) moves price as much as the model:
a 116508 green "John Mayer" trades ~65% above a 116508 champagne. Where a
short reference hides dial variety, each dial becomes its own watch row
(dial_variant set); the dial_variant IS NULL row remains as the reference-
level parent/fallback bucket.

Revision ID: 006
Revises: 005
Create Date: 2026-07-03
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("watches", sa.Column("dial_variant", sa.String(50)))
    # One parent row per (brand, ref); variants unique within their ref
    op.drop_constraint("uq_watch_brand_ref", "watches", type_="unique")
    op.create_index(
        "uq_watch_brand_ref_parent",
        "watches",
        ["brand_id", "reference_number"],
        unique=True,
        postgresql_where=sa.text("dial_variant IS NULL"),
    )
    op.create_index(
        "uq_watch_brand_ref_variant",
        "watches",
        ["brand_id", "reference_number", "dial_variant"],
        unique=True,
        postgresql_where=sa.text("dial_variant IS NOT NULL"),
    )

    op.add_column("portfolio_holdings", sa.Column("dial_variant", sa.String(50)))


def downgrade() -> None:
    op.drop_column("portfolio_holdings", "dial_variant")
    op.drop_index("uq_watch_brand_ref_variant", table_name="watches")
    op.drop_index("uq_watch_brand_ref_parent", table_name="watches")
    op.create_unique_constraint(
        "uq_watch_brand_ref", "watches", ["brand_id", "reference_number"]
    )
    op.drop_column("watches", "dial_variant")
