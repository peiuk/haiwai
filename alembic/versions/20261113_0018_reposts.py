"""repost points at the original content

Revision ID: 20261113_0018
Revises: 20261113_0017
Create Date: 2026-11-13
"""

import sqlalchemy as sa
from alembic import op

revision = "20261113_0018"
down_revision = "20261113_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("content", sa.Column("repost_of_id", sa.String(36), nullable=True))


def downgrade() -> None:
    op.drop_column("content", "repost_of_id")
