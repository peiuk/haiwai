"""site-wide switches (review on/off per content kind)

Revision ID: 20261115_0036
Revises: 20261115_0035
Create Date: 2026-11-15
"""

import sqlalchemy as sa
from alembic import op

revision = "20261115_0036"
down_revision = "20261115_0035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "site_setting",
        sa.Column("key", sa.String(32), primary_key=True),
        sa.Column("value", sa.String(64), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("site_setting")
