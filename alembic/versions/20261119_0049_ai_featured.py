"""content.ai_featured_until: AI 设的精选在这个时间自动取消（人工设的为空，不过期）

Revision ID: 20261119_0049
Revises: 20261118_0048
Create Date: 2026-11-19
"""

import sqlalchemy as sa
from alembic import op

revision = "20261119_0049"
down_revision = "20261118_0048"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("content", sa.Column("ai_featured_until", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("content") as batch:
        batch.drop_column("ai_featured_until")
