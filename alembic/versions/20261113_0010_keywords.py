"""searchable keywords on content

Revision ID: 20261113_0010
Revises: 20261113_0009
Create Date: 2026-11-13
"""

import sqlalchemy as sa
from alembic import op

revision = "20261113_0010"
down_revision = "20261113_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("content", sa.Column("keywords_json", sa.Text(), nullable=False, server_default="[]"))


def downgrade() -> None:
    op.drop_column("content", "keywords_json")
