"""rate_hit table (shared login / register throttle) and indexes on dm and upload lookups

Revision ID: 20261116_0040
Revises: 20261116_0039
Create Date: 2026-11-16
"""

import sqlalchemy as sa
from alembic import op

revision = "20261116_0040"
down_revision = "20261116_0039"
branch_labels = None
depends_on = None

INDEXES = [
    ("ix_dm_message_thread", "dm_message", ["thread_id"]),
    ("ix_dm_thread_high", "dm_thread", ["user_high"]),
    ("ix_upload_owner", "upload_object", ["owner_id"]),
]


def upgrade() -> None:
    op.create_table(
        "rate_hit",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("key", sa.String(160), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_rate_hit_key_at", "rate_hit", ["key", "at"])
    for name, table, columns in INDEXES:
        op.create_index(name, table, columns)


def downgrade() -> None:
    for name, table, _columns in INDEXES:
        op.drop_index(name, table_name=table)
    op.drop_table("rate_hit")
