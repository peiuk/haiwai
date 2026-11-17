"""room slots and push review

Revision ID: 20261117_0042
Revises: 20261117_0041
Create Date: 2026-11-17
"""

import sqlalchemy as sa
from alembic import op

revision = "20261117_0042"
down_revision = "20261117_0041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 已有的推送都是不经审核直接进频道的，保持已通过
    op.add_column("room_post_push", sa.Column("status", sa.String(16), nullable=False, server_default="approved"))
    op.create_table(
        "channel_room_slot",
        sa.Column("channel_id", sa.String(36), sa.ForeignKey("channel.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("room_id", sa.String(36), sa.ForeignKey("channel.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("label", sa.String(16), nullable=False, server_default=""),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    # 原来房间靠父频道自动列在频道里：换成房间位后先把现有的都转过去，上线时前台不会少房间
    op.execute(
        "INSERT INTO channel_room_slot (channel_id, room_id) "
        "SELECT parent_channel_id, id FROM channel "
        "WHERE kind = 'room' AND parent_channel_id IN (SELECT id FROM channel)"
    )


def downgrade() -> None:
    op.drop_table("channel_room_slot")
    op.drop_column("room_post_push", "status")
