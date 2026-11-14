"""accounts can show a city next to the handle

Revision ID: 20261113_0025
Revises: 20261113_0024
Create Date: 2026-11-13
"""

import sqlalchemy as sa
from alembic import op

revision = "20261113_0025"
down_revision = "20261113_0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("app_user", sa.Column("city_label", sa.String(12)))


def downgrade() -> None:
    op.drop_column("app_user", "city_label")
