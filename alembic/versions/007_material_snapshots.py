"""Material-stratified weekly snapshots

Case material moves price like the model does (two-tone Datejust +42% over
steel at family level), so weekly medians are stored per material bucket to
stop material-mix drift from reading as price moves.

Revision ID: 007
Revises: 006
Create Date: 2026-07-03
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "price_snapshots",
        sa.Column("material", sa.String(20), nullable=False, server_default="all"),
    )
    op.drop_constraint(
        "uq_snapshot_week_family_type", "price_snapshots", type_="unique"
    )
    op.create_unique_constraint(
        "uq_snapshot_week_family_material_type",
        "price_snapshots",
        ["snapshot_date", "brand", "family", "material", "price_type"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_snapshot_week_family_material_type", "price_snapshots", type_="unique"
    )
    op.create_unique_constraint(
        "uq_snapshot_week_family_type",
        "price_snapshots",
        ["snapshot_date", "brand", "family", "price_type"],
    )
    op.drop_column("price_snapshots", "material")
