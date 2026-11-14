"""optional image on room/post replies

Revision ID: 20261114_0028
Revises: 20261113_0027
Create Date: 2026-11-14
"""

import sqlalchemy as sa
from alembic import op

revision = "20261114_0028"
down_revision = "20261113_0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "room_comment",
        sa.Column("image_key", sa.String(64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("room_comment", "image_key")
