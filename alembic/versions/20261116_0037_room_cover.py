"""room cover image (series room page)

Revision ID: 20261116_0037
Revises: 20261115_0036
Create Date: 2026-11-16
"""

import sqlalchemy as sa
from alembic import op

revision = "20261116_0037"
down_revision = "20261115_0036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("channel", sa.Column("cover_key", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("channel", "cover_key")
