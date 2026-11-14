"""reports against a user profile

Revision ID: 20261113_0019
Revises: 20261113_0018
Create Date: 2026-11-13
"""

import sqlalchemy as sa
from alembic import op

revision = "20261113_0019"
down_revision = "20261113_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("moderation_case") as batch:
        batch.alter_column("content_id", existing_type=sa.String(36), nullable=True)
    op.add_column("moderation_case", sa.Column("reported_user_id", sa.String(36), nullable=True))


def downgrade() -> None:
    op.drop_column("moderation_case", "reported_user_id")
    with op.batch_alter_table("moderation_case") as batch:
        batch.alter_column("content_id", existing_type=sa.String(36), nullable=False)
