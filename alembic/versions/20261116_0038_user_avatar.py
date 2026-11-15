"""user avatar image

Revision ID: 20261116_0038
Revises: 20261116_0037
Create Date: 2026-11-16
"""

import sqlalchemy as sa
from alembic import op

revision = "20261116_0038"
down_revision = "20261116_0037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("app_user", sa.Column("avatar_key", sa.String(32), nullable=True))


def downgrade() -> None:
    op.drop_column("app_user", "avatar_key")
