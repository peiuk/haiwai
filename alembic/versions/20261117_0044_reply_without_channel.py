"""replies on posts that are not in any channel (room_comment.room_id nullable)

Revision ID: 20261117_0044
Revises: 20261117_0043
Create Date: 2026-11-17
"""

import sqlalchemy as sa
from alembic import op

revision = "20261117_0044"
down_revision = "20261117_0043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 发到「我的动态」的帖子不属于任何频道：它下面的回复没有 room_id 可填，原来的必填约束让这类帖子根本回复不了
    with op.batch_alter_table("room_comment") as batch:
        batch.alter_column("room_id", existing_type=sa.String(36), nullable=True)


def downgrade() -> None:
    op.execute("DELETE FROM room_comment WHERE room_id IS NULL")
    with op.batch_alter_table("room_comment") as batch:
        batch.alter_column("room_id", existing_type=sa.String(36), nullable=False)
