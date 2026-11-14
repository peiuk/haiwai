"""content images and upload grants

Revision ID: 20261113_0008
Revises: 20261113_0007
Create Date: 2026-11-13
"""

import sqlalchemy as sa
from alembic import op

revision = "20261113_0008"
down_revision = "20261113_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("content", sa.Column("image_key", sa.String(64)))
    op.add_column("dm_message", sa.Column("image_key", sa.String(64)))
    op.create_table(
        "upload_object",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content_type", sa.String(64), nullable=False),
        sa.Column("stored", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("upload_object")
    op.drop_column("dm_message", "image_key")
    op.drop_column("content", "image_key")
