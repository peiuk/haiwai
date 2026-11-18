"""copy the original post's images / video onto existing reposts

转发原来只抄了标题和文字，原帖的视频图片在转发卡和转发详情里都看不到。新转发会带上；这里补齐已有的。

Revision ID: 20261118_0048
Revises: 20261118_0047
Create Date: 2026-11-18
"""

from alembic import op

revision = "20261118_0048"
down_revision = "20261118_0047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE content SET "
        "image_key = (SELECT o.image_key FROM content o WHERE o.id = content.repost_of_id), "
        "image_keys_json = COALESCE((SELECT o.image_keys_json FROM content o WHERE o.id = content.repost_of_id), '[]'), "
        "video_key = (SELECT o.video_key FROM content o WHERE o.id = content.repost_of_id) "
        "WHERE type = 'repost' AND repost_of_id IS NOT NULL"
    )


def downgrade() -> None:
    pass  # 数据修正，无需回滚
