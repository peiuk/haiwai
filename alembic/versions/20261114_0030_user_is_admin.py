"""user is_admin

Revision ID: 20261114_0030
Revises: 20261114_0029
Create Date: 2026-11-14
"""

import sqlalchemy as sa
from alembic import op

revision = "20261114_0030"
down_revision = "20261114_0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "app_user",
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("app_user", "is_admin")
