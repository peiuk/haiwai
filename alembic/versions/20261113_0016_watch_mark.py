"""private want or watched mark on room entries

Revision ID: 20261113_0016
Revises: 20261113_0015
Create Date: 2026-11-13
"""

import sqlalchemy as sa
from alembic import op

revision = "20261113_0016"
down_revision = "20261113_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_item_progress",
        sa.Column("watch_mark", sa.String(16), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("user_item_progress", "watch_mark")
