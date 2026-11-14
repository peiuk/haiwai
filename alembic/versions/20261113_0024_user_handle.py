"""accounts keep a public handle and an avatar tone

Revision ID: 20261113_0024
Revises: 20261113_0023
Create Date: 2026-11-13
"""

import sqlalchemy as sa
from alembic import op

revision = "20261113_0024"
down_revision = "20261113_0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("app_user", sa.Column("handle", sa.String(20)))
    op.add_column("app_user", sa.Column("avatar_tone", sa.String(1), nullable=False, server_default="a"))
    op.create_index("ix_app_user_handle", "app_user", ["handle"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_app_user_handle", table_name="app_user")
    op.drop_column("app_user", "avatar_tone")
    op.drop_column("app_user", "handle")
