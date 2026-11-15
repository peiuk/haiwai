"""admin ops: channel certification, featured content, audit detail

Revision ID: 20261115_0032
Revises: 20261114_0031
Create Date: 2026-11-15
"""

import sqlalchemy as sa
from alembic import op

revision = "20261115_0032"
down_revision = "20261114_0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("channel", sa.Column("is_certified", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("content", sa.Column("featured_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("audit_log", sa.Column("detail", sa.String(300), nullable=True))


def downgrade() -> None:
    op.drop_column("audit_log", "detail")
    op.drop_column("content", "featured_at")
    op.drop_column("channel", "is_certified")
