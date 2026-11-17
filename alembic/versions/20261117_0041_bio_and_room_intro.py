"""user bio and room intro

Revision ID: 20261117_0041
Revises: 20261116_0040
Create Date: 2026-11-17
"""

import sqlalchemy as sa
from alembic import op

revision = "20261117_0041"
down_revision = "20261116_0040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("app_user", sa.Column("bio", sa.String(250), nullable=True))
    op.add_column("channel", sa.Column("intro", sa.String(250), nullable=True))


def downgrade() -> None:
    op.drop_column("channel", "intro")
    op.drop_column("app_user", "bio")
