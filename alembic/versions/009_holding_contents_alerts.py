"""Add holding completeness + wishlist flag + price alerts

Revision ID: 009
Revises: 008
Create Date: 2026-07-04
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("portfolio_holdings", sa.Column("contents", sa.String(20)))
    op.add_column(
        "portfolio_holdings",
        sa.Column("is_wishlist", sa.Boolean, nullable=False, server_default="false"),
    )
    op.create_table(
        "price_alerts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("brand", sa.String(100), nullable=False),
        sa.Column("family", sa.String(100), nullable=False),
        sa.Column("reference_number", sa.String(50)),
        sa.Column("dial_variant", sa.String(50)),
        sa.Column("threshold_usd", sa.Float, nullable=False),
        sa.Column("direction", sa.String(5), nullable=False),  # "above"/"below"
        sa.Column("email", sa.String(200)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("price_alerts")
    op.drop_column("portfolio_holdings", "is_wishlist")
    op.drop_column("portfolio_holdings", "contents")
