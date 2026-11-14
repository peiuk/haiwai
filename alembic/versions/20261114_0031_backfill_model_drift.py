"""backfill tables and columns that existed only in models

开发库靠 create_all + 手写补列一直有这些表和列，迁移里却从没建过：
按迁移建出来的生产库会缺通知表和房间审核字段。tests/test_migrations.py 发现并防止再犯。

Revision ID: 20261114_0031
Revises: 20261114_0030
Create Date: 2026-11-14
"""

import sqlalchemy as sa
from alembic import op

revision = "20261114_0031"
down_revision = "20261114_0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "event_cluster",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("key", sa.String(128), nullable=False, unique=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("source_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "notification",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("body", sa.String(200), nullable=False),
        sa.Column("content_id", sa.String(36), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_notification_user_id", "notification", ["user_id"])
    op.add_column("channel", sa.Column("parent_channel_id", sa.String(36), nullable=True))
    # 已有频道沿用开发库补列时的取值：视为已审核
    op.add_column("channel", sa.Column("review_status", sa.String(16), nullable=False, server_default="approved"))
    op.add_column("content", sa.Column("content_hash", sa.String(64), nullable=True))
    op.create_index("ix_content_content_hash", "content", ["content_hash"], unique=True)
    op.add_column("content", sa.Column("ai_status", sa.String(16), nullable=False, server_default="pending"))
    op.add_column("content", sa.Column("event_cluster_id", sa.String(36), nullable=True))


def downgrade() -> None:
    op.drop_column("content", "event_cluster_id")
    op.drop_column("content", "ai_status")
    op.drop_index("ix_content_content_hash", table_name="content")
    op.drop_column("content", "content_hash")
    op.drop_column("channel", "review_status")
    op.drop_column("channel", "parent_channel_id")
    op.drop_index("ix_notification_user_id", table_name="notification")
    op.drop_table("notification")
    op.drop_table("event_cluster")
