"""video posts keep a file key and a rights confirmation

Revision ID: 20261113_0023
Revises: 20261113_0022
Create Date: 2026-11-13
"""

import sqlalchemy as sa
from alembic import op

revision = "20261113_0023"
down_revision = "20261113_0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("content", sa.Column("video_key", sa.String(64)))
    op.add_column("content", sa.Column("rights_confirmed", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("content", "rights_confirmed")
    op.drop_column("content", "video_key")
