"""record requests to open a country without enabling it

Revision ID: 20261113_0020
Revises: 20261113_0019
Create Date: 2026-11-13
"""

import sqlalchemy as sa
from alembic import op

revision = "20261113_0020"
down_revision = "20261113_0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "region_open_request",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("region_code", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "region_code", name="uq_region_open"),
    )


def downgrade() -> None:
    op.drop_table("region_open_request")
