"""region preference, refresh sessions, content script fields

Revision ID: 20261113_0005
Revises: 20261113_0004
Create Date: 2026-11-13
"""

import sqlalchemy as sa
from alembic import op

revision = "20261113_0005"
down_revision = "20261113_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("content", sa.Column("title_hant", sa.String(200)))
    op.add_column("content", sa.Column("summary_hant", sa.String(500)))
    op.create_table(
        "user_region_pref",
        sa.Column("user_id", sa.String(36), sa.ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("region_code", sa.String(16), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("locked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("consent_id", sa.String(36)),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "refresh_session",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_refresh_session_user_id", "refresh_session", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_refresh_session_user_id", table_name="refresh_session")
    op.drop_table("refresh_session")
    op.drop_table("user_region_pref")
    op.drop_column("content", "summary_hant")
    op.drop_column("content", "title_hant")
