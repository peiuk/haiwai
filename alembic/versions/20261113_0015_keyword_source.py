"""whether post keywords came from the official suggestion

Revision ID: 20261113_0015
Revises: 20261113_0014
Create Date: 2026-11-13
"""

import sqlalchemy as sa
from alembic import op

revision = "20261113_0015"
down_revision = "20261113_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("content", sa.Column("keyword_source", sa.String(16), nullable=True))


def downgrade() -> None:
    op.drop_column("content", "keyword_source")
