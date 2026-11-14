"""embed links and playback consent

Revision ID: 20261113_0009
Revises: 20261113_0008
Create Date: 2026-11-13
"""

import sqlalchemy as sa
from alembic import op

revision = "20261113_0009"
down_revision = "20261113_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("content", sa.Column("embed_provider_code", sa.String(32)))
    op.add_column("content", sa.Column("embed_media_id", sa.String(32)))
    op.add_column("content", sa.Column("embed_source_url", sa.Text()))
    op.add_column("content", sa.Column("embed_status", sa.String(16), nullable=False, server_default="none"))
    op.create_table(
        "user_consent_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider_code", sa.String(32), nullable=False),
        sa.Column("scope", sa.String(16), nullable=False),
        sa.Column("policy_version", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("user_consent_log")
    op.drop_column("content", "embed_status")
    op.drop_column("content", "embed_source_url")
    op.drop_column("content", "embed_media_id")
    op.drop_column("content", "embed_provider_code")
