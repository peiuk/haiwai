"""comment likes on room and post replies

Revision ID: 20261113_0026
Revises: 20261113_0025
Create Date: 2026-11-13
"""

import sqlalchemy as sa
from alembic import op

revision = "20261113_0026"
down_revision = "20261113_0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "comment_like",
        sa.Column("comment_id", sa.String(36), sa.ForeignKey("room_comment.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("comment_like")
