"""content.ai_channel_id / ai_channel_reason: AI 建议把帖子移去的频道和理由（管理员确认后才移）

Revision ID: 20261120_0050
Revises: 20261119_0049
Create Date: 2026-11-20
"""

import sqlalchemy as sa
from alembic import op

revision = "20261120_0050"
down_revision = "20261119_0049"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("content", sa.Column("ai_channel_id", sa.String(36), nullable=True))
    op.add_column("content", sa.Column("ai_channel_reason", sa.String(200), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("content") as batch:
        batch.drop_column("ai_channel_reason")
        batch.drop_column("ai_channel_id")
