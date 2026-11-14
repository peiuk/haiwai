"""channels, subscriptions, and the following feed

Revision ID: 20261113_0002
Revises: 20261113_0001
Create Date: 2026-11-13
"""

import sqlalchemy as sa
from alembic import op

revision = "20261113_0002"
down_revision = "20261113_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_user",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("display_name", sa.String(40), nullable=False),
        sa.Column("script_pref", sa.String(8), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("phone_verified", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "channel",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("code", sa.String(48), nullable=False, unique=True),
        sa.Column("name_hans", sa.String(64), nullable=False),
        sa.Column("name_hant", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("visibility", sa.String(16), nullable=False),
        sa.Column("region_code", sa.String(16), nullable=False),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("app_user.id")),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("subscriber_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "channel_subscription",
        sa.Column("user_id", sa.String(36), sa.ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("channel_id", sa.String(36), sa.ForeignKey("channel.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("is_muted", sa.Boolean(), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "content",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("summary", sa.String(500)),
        sa.Column("canonical_url", sa.Text()),
        sa.Column("source_name", sa.String(96)),
        sa.Column("licence_ref", sa.Text()),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("type <> 'news' OR canonical_url IS NOT NULL", name="chk_news_link"),
        sa.CheckConstraint("type <> 'listing' OR expires_at IS NOT NULL", name="chk_listing_expiry"),
    )
    op.create_table(
        "channel_item",
        sa.Column("channel_id", sa.String(36), sa.ForeignKey("channel.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("content_id", sa.String(36), sa.ForeignKey("content.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("pinned", sa.Boolean(), nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("channel_item")
    op.drop_table("content")
    op.drop_table("channel_subscription")
    op.drop_table("channel")
    op.drop_table("app_user")
