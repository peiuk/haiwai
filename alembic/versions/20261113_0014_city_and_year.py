"""city topic on posts and year on film entries

Revision ID: 20261113_0014
Revises: 20261113_0013
Create Date: 2026-11-13
"""

import sqlalchemy as sa
from alembic import op

revision = "20261113_0014"
down_revision = "20261113_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("content", sa.Column("city_topic", sa.String(12), nullable=True))
    op.add_column("channel_item", sa.Column("year", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("channel_item", "year")
    op.drop_column("content", "city_topic")
