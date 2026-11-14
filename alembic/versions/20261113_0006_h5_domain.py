"""listings, reactions, room pushes, and direct messages

Revision ID: 20261113_0006
Revises: 20261113_0005
Create Date: 2026-11-13
"""

import sqlalchemy as sa
from alembic import op

revision = "20261113_0006"
down_revision = "20261113_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("app_user", sa.Column("dm_allow_strangers", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("app_user", sa.Column("feed_seen_at", sa.DateTime(timezone=True)))
    op.add_column("channel", sa.Column("category", sa.String(16)))
    op.add_column("channel_item", sa.Column("origin_room_id", sa.String(36)))
    op.add_column("user_region_pref", sa.Column("browse_region_code", sa.String(16)))
    op.create_table(
        "listing_ext",
        sa.Column("content_id", sa.String(36), sa.ForeignKey("content.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("category", sa.String(16), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("area", sa.String(80), nullable=False),
        sa.Column("price_amount", sa.String(32), nullable=False),
        sa.Column("price_unit", sa.String(16)),
        sa.Column("currency", sa.String(8), nullable=False),
        sa.Column("contact", sa.String(120), nullable=False),
        sa.Column("attrs_json", sa.Text(), nullable=False),
        sa.Column("closed_reason", sa.String(16)),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "contact_view",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content_id", sa.String(36), sa.ForeignKey("content.id", ondelete="CASCADE"), nullable=False),
        sa.Column("viewed_on", sa.String(10), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "content_reaction",
        sa.Column("user_id", sa.String(36), sa.ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("content_id", sa.String(36), sa.ForeignKey("content.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("liked", sa.Boolean(), nullable=False),
        sa.Column("favorited", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "room_post_push",
        sa.Column("content_id", sa.String(36), sa.ForeignKey("content.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("room_id", sa.String(36), sa.ForeignKey("channel.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel_id", sa.String(36), sa.ForeignKey("channel.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pushed_by", sa.String(36), sa.ForeignKey("app_user.id"), nullable=False),
        sa.Column("pushed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "user_follow",
        sa.Column("user_id", sa.String(36), sa.ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("target_id", sa.String(36), sa.ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "user_block",
        sa.Column("user_id", sa.String(36), sa.ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("target_id", sa.String(36), sa.ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "dm_thread",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_low", sa.String(36), sa.ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_high", sa.String(36), sa.ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("listing_inquiry", sa.Boolean(), nullable=False),
        sa.Column("listing_ref", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_low", "user_high", name="uq_dm_pair"),
    )
    op.create_table(
        "dm_message",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("thread_id", sa.String(36), sa.ForeignKey("dm_thread.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sender_id", sa.String(36), sa.ForeignKey("app_user.id"), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("body", sa.String(1000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("dm_message")
    op.drop_table("dm_thread")
    op.drop_table("user_block")
    op.drop_table("user_follow")
    op.drop_table("room_post_push")
    op.drop_table("content_reaction")
    op.drop_table("contact_view")
    op.drop_table("listing_ext")
    op.drop_column("user_region_pref", "browse_region_code")
    op.drop_column("channel_item", "origin_room_id")
    op.drop_column("channel", "category")
    op.drop_column("app_user", "feed_seen_at")
    op.drop_column("app_user", "dm_allow_strangers")
