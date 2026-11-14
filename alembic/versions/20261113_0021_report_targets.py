"""reports can target a room or a comment

Revision ID: 20261113_0021
Revises: 20261113_0020
Create Date: 2026-11-13
"""

import sqlalchemy as sa
from alembic import op

revision = "20261113_0021"
down_revision = "20261113_0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("moderation_case", sa.Column("reported_channel_id", sa.String(36)))
    op.add_column("moderation_case", sa.Column("reported_comment_id", sa.String(36)))


def downgrade() -> None:
    op.drop_column("moderation_case", "reported_comment_id")
    op.drop_column("moderation_case", "reported_channel_id")
