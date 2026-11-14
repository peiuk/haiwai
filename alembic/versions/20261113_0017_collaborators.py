"""room collaborators

Revision ID: 20261113_0017
Revises: 20261113_0016
Create Date: 2026-11-13
"""

import sqlalchemy as sa
from alembic import op

revision = "20261113_0017"
down_revision = "20261113_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "channel_collaborator",
        sa.Column("channel_id", sa.String(36), sa.ForeignKey("channel.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("channel_collaborator")
