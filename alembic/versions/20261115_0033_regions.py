"""regions opened from admin, channel sort order

Revision ID: 20261115_0033
Revises: 20261115_0032
Create Date: 2026-11-15
"""

import sqlalchemy as sa
from alembic import op

revision = "20261115_0033"
down_revision = "20261115_0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "region",
        sa.Column("code", sa.String(8), primary_key=True),
        sa.Column("name_hans", sa.String(32), nullable=False),
        sa.Column("city", sa.String(32), nullable=False, server_default=""),
        sa.Column("is_open", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.add_column("channel", sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("channel", "sort_order")
    op.drop_table("region")
