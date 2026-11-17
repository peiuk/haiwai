"""content.bg_style: colored background for short text posts

Revision ID: 20261117_0046
Revises: 20261117_0045
Create Date: 2026-11-17
"""

import sqlalchemy as sa
from alembic import op

revision = "20261117_0046"
down_revision = "20261117_0045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("content", sa.Column("bg_style", sa.String(16), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("content") as batch:
        batch.drop_column("bg_style")
