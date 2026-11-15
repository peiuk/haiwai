"""room ban: members the owner removed and barred from rejoining

Revision ID: 20261116_0039
Revises: 20261116_0038
Create Date: 2026-11-16
"""

import sqlalchemy as sa
from alembic import op

revision = "20261116_0039"
down_revision = "20261116_0038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "room_ban",
        sa.Column("room_id", sa.String(36), sa.ForeignKey("channel.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("room_ban")
