"""consent, reports, subscriptions, and search

Revision ID: 20261113_0004
Revises: 20261113_0003
Create Date: 2026-11-13
"""

import sqlalchemy as sa
from alembic import op

revision = "20261113_0004"
down_revision = "20261113_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("channel_subscription", sa.Column("last_read_at", sa.DateTime(timezone=True)))
    op.add_column(
        "channel_subscription",
        sa.Column("unread_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "consent_record",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("purpose", sa.String(48), nullable=False),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("granted", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "moderation_case",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("content_id", sa.String(36), sa.ForeignKey("content.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reporter_id", sa.String(36), sa.ForeignKey("app_user.id"), nullable=False),
        sa.Column("reason", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("decision", sa.String(24)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "audit_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("actor_id", sa.String(36)),
        sa.Column("action", sa.String(48), nullable=False),
        sa.Column("target_type", sa.String(24)),
        sa.Column("target_id", sa.String(36)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("moderation_case")
    op.drop_table("consent_record")
    op.drop_column("channel_subscription", "unread_count")
    op.drop_column("channel_subscription", "last_read_at")
