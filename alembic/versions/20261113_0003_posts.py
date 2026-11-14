"""author, phone, and post body

Revision ID: 20261113_0003
Revises: 20261113_0002
Create Date: 2026-11-13
"""

import sqlalchemy as sa
from alembic import op

revision = "20261113_0003"
down_revision = "20261113_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("app_user", sa.Column("phone", sa.String(32)))
    op.create_index("ix_app_user_phone", "app_user", ["phone"], unique=True)
    op.add_column("content", sa.Column("author_id", sa.String(36), sa.ForeignKey("app_user.id")))
    op.add_column("content", sa.Column("body", sa.Text()))


def downgrade() -> None:
    op.drop_column("content", "body")
    op.drop_column("content", "author_id")
    op.drop_index("ix_app_user_phone", table_name="app_user")
    op.drop_column("app_user", "phone")
