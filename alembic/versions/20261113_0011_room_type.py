"""room display type

Revision ID: 20261113_0011
Revises: 20261113_0010
Create Date: 2026-11-13
"""

import sqlalchemy as sa
from alembic import op

revision = "20261113_0011"
down_revision = "20261113_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("channel", sa.Column("room_type", sa.String(16), nullable=False, server_default="general"))


def downgrade() -> None:
    op.drop_column("channel", "room_type")
