"""enable pg_trgm and citext (postgis dropped: unused, and missing on most stock PostgreSQL installs)

Revision ID: 20261113_0001
Revises:
Create Date: 2026-11-13
"""

from alembic import op

revision = "20261113_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 扩展只有 Postgres 有；在 SQLite 上跳过，整条迁移链才能在开发库和测试里跑通。
    if op.get_bind().dialect.name != "postgresql":
        return
    # 不再建 postgis：代码里没有任何地理查询，而普通 PostgreSQL / 托管库多数没装它，第一条迁移就会失败。
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("DROP EXTENSION IF EXISTS citext")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
    op.execute("DROP EXTENSION IF EXISTS postgis")
