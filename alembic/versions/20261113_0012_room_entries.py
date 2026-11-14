"""series and film entry order, private progress

Revision ID: 20261113_0012
Revises: 20261113_0011
Create Date: 2026-11-13
"""

import sqlalchemy as sa
from alembic import op

revision = "20261113_0012"
down_revision = "20261113_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("channel_item", sa.Column("sort_key", sa.String(16), nullable=False, server_default=""))
    op.add_column("channel_item", sa.Column("season", sa.Integer(), nullable=True))
    op.add_column("channel_item", sa.Column("episode", sa.Integer(), nullable=True))
    op.create_table(
        "user_item_progress",
        sa.Column("user_id", sa.String(36), sa.ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("content_id", sa.String(36), sa.ForeignKey("content.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("user_item_progress")
    op.drop_column("channel_item", "episode")
    op.drop_column("channel_item", "season")
    op.drop_column("channel_item", "sort_key")
