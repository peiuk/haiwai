"""room comments, private join requests, message read time

Revision ID: 20261113_0007
Revises: 20261113_0006
Create Date: 2026-11-13
"""

import sqlalchemy as sa
from alembic import op

revision = "20261113_0007"
down_revision = "20261113_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("channel", sa.Column("is_private", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("dm_message", sa.Column("read_at", sa.DateTime(timezone=True)))
    op.create_table(
        "room_comment",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("room_id", sa.String(36), sa.ForeignKey("channel.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content_id", sa.String(36)),
        sa.Column("parent_id", sa.String(36)),
        sa.Column("author_id", sa.String(36), sa.ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("body", sa.String(1000), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("mention_count", sa.Integer(), nullable=False),
        sa.Column("keyword_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("removed_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "room_join_request",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("room_id", sa.String(36), sa.ForeignKey("channel.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("room_id", "user_id", name="uq_room_join"),
    )


def downgrade() -> None:
    op.drop_table("room_join_request")
    op.drop_table("room_comment")
    op.drop_column("dm_message", "read_at")
    op.drop_column("channel", "is_private")
