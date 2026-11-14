"""content view count

Revision ID: 20261114_0029
Revises: 20261114_0028
Create Date: 2026-11-14
"""

import sqlalchemy as sa
from alembic import op

revision = "20261114_0029"
down_revision = "20261114_0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "content",
        sa.Column("view_count", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("content", "view_count")
