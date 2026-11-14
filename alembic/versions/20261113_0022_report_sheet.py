"""report reasons match the sheet, including a guest note

Revision ID: 20261113_0022
Revises: 20261113_0021
Create Date: 2026-11-13
"""

import sqlalchemy as sa
from alembic import op

revision = "20261113_0022"
down_revision = "20261113_0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("moderation_case", sa.Column("detail", sa.String(300), nullable=False, server_default=""))
    with op.batch_alter_table("moderation_case") as batch:
        batch.alter_column("reporter_id", existing_type=sa.String(36), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("moderation_case") as batch:
        batch.alter_column("reporter_id", existing_type=sa.String(36), nullable=False)
    op.drop_column("moderation_case", "detail")
