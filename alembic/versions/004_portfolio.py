"""Add portfolio_holdings for tracking a user's own watches

Revision ID: 004
Revises: 003
Create Date: 2026-07-01
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "portfolio_holdings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("nickname", sa.String(200)),
        sa.Column("brand", sa.String(100), nullable=False),
        sa.Column("family", sa.String(100), nullable=False),
        sa.Column("reference_number", sa.String(50)),
        sa.Column("purchase_price_usd", sa.Float),
        sa.Column("purchase_date", sa.Date),
        sa.Column("condition", sa.String(20)),
        sa.Column("notes", sa.Text),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("portfolio_holdings")
