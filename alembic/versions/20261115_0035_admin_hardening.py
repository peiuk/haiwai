"""admin hardening: roles, two-factor, timed suspension, audit source, review claims, blocked terms, indexes

Revision ID: 20261115_0035
Revises: 20261115_0034
Create Date: 2026-11-15
"""

import sqlalchemy as sa
from alembic import op

revision = "20261115_0035"
down_revision = "20261115_0034"
branch_labels = None
depends_on = None

INDEXES = [
    ("ix_content_status_created", "content", ["status", "created_at"]),
    ("ix_content_author", "content", ["author_id"]),
    ("ix_channel_item_content", "channel_item", ["content_id"]),
    ("ix_case_status_created", "moderation_case", ["status", "created_at"]),
    ("ix_case_content", "moderation_case", ["content_id"]),
    ("ix_comment_status_created", "room_comment", ["status", "created_at"]),
    ("ix_comment_content", "room_comment", ["content_id"]),
    ("ix_audit_created", "audit_log", ["created_at"]),
    ("ix_audit_target", "audit_log", ["target_type", "target_id"]),
]


def upgrade() -> None:
    op.add_column("app_user", sa.Column("is_super", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("app_user", sa.Column("totp_secret", sa.String(64), nullable=True))
    op.add_column("app_user", sa.Column("suspended_until", sa.DateTime(timezone=True), nullable=True))
    op.add_column("app_user", sa.Column("suspend_reason", sa.String(300), nullable=True))
    # 在分级之前设的管理员本来就能做全部操作：升级后保持不变，都算超级管理员
    op.execute("UPDATE app_user SET is_super = is_admin")
    op.add_column("audit_log", sa.Column("ip", sa.String(64), nullable=True))
    op.add_column("audit_log", sa.Column("user_agent", sa.String(200), nullable=True))
    op.add_column("refresh_session", sa.Column("admin", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_table(
        "review_claim",
        sa.Column("target_type", sa.String(16), primary_key=True),
        sa.Column("target_id", sa.String(36), primary_key=True),
        sa.Column("admin_id", sa.String(36), sa.ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "blocked_term",
        sa.Column("term", sa.String(64), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    for name, table, columns in INDEXES:
        op.create_index(name, table, columns)
    if op.get_bind().dialect.name == "postgresql":
        # 后台按标题搜索用的是 LIKE '%词%'，普通索引帮不上；三元组索引可以。
        # 建扩展需要数据库超级用户权限（docker-compose 里的账号有）；没权限时跳过，搜索照常能用，只是数据多了会慢。
        with op.get_bind().begin_nested() as attempt:
            try:
                op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
                op.execute("CREATE INDEX ix_content_title_trgm ON content USING gin (title gin_trgm_ops)")
            except sa.exc.DBAPIError:
                attempt.rollback()


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_content_title_trgm")
    for name, table, _columns in INDEXES:
        op.drop_index(name, table_name=table)
    op.drop_table("blocked_term")
    op.drop_table("review_claim")
    op.drop_column("refresh_session", "admin")
    op.drop_column("audit_log", "user_agent")
    op.drop_column("audit_log", "ip")
    op.drop_column("app_user", "suspend_reason")
    op.drop_column("app_user", "suspended_until")
    op.drop_column("app_user", "totp_secret")
    op.drop_column("app_user", "is_super")
