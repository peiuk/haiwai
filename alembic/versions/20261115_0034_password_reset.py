"""one-time password reset tokens

Revision ID: 20261115_0034
Revises: 20261115_0033
Create Date: 2026-11-15
"""

import sqlalchemy as sa
from alembic import op

revision = "20261115_0034"
down_revision = "20261115_0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "password_reset",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("password_reset")
