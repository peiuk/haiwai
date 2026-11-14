"""multiple listing images stored as a JSON array on content

Revision ID: 20261113_0027
Revises: 20261113_0026
Create Date: 2026-11-13
"""

import sqlalchemy as sa
from alembic import op

revision = "20261113_0027"
down_revision = "20261113_0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "content",
        sa.Column("image_keys_json", sa.Text(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("content", "image_keys_json")
