"""user trusted (whitelist)

Revision ID: 20261117_0043
Revises: 20261117_0042
Create Date: 2026-11-17
"""

import sqlalchemy as sa
from alembic import op

revision = "20261117_0043"
down_revision = "20261117_0042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("app_user", sa.Column("is_trusted", sa.Boolean, nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("app_user", "is_trusted")
