"""original video rights confirmation

Revision ID: 20261113_0013
Revises: 20261113_0012
Create Date: 2026-11-13
"""

import sqlalchemy as sa
from alembic import op

revision = "20261113_0013"
down_revision = "20261113_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "channel_item",
        sa.Column("rights_confirmed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("channel_item", "rights_confirmed")
