"""re-enable in-site playback for YouTube / Bilibili embeds wrongly saved as fallback

之前判断能否嵌入时查的是观看页（YouTube 观看页带 X-Frame-Options: SAMEORIGIN），
所以这两个平台的外链都被存成了 fallback（只能去原站看）。实际放进 iframe 的是 /embed/ 播放器，允许嵌入。

Revision ID: 20261118_0047
Revises: 20261117_0046
Create Date: 2026-11-18
"""

from alembic import op

revision = "20261118_0047"
down_revision = "20261117_0046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE content SET embed_status = 'embeddable' "
        "WHERE embed_status = 'fallback' AND embed_provider_code IN ('youtube', 'bilibili')"
    )


def downgrade() -> None:
    pass  # 数据修正，无需回滚
