"""site_setting.value widened to text (holds the SMTP settings as JSON)

Revision ID: 20261117_0045
Revises: 20261117_0044
Create Date: 2026-11-17
"""

import sqlalchemy as sa
from alembic import op

revision = "20261117_0045"
down_revision = "20261117_0044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("site_setting") as batch:
        batch.alter_column("value", existing_type=sa.String(64), type_=sa.Text(), existing_nullable=False)


def downgrade() -> None:
    # 发信邮箱那一行放不回 64 个字符：降级就丢掉它，回去后在后台重新填
    op.execute("DELETE FROM site_setting WHERE key = 'mail'")
    with op.batch_alter_table("site_setting") as batch:
        batch.alter_column("value", existing_type=sa.Text(), type_=sa.String(64), existing_nullable=False)
