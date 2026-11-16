"""每日清理：没用上的上传文件、过期的限流记录。由 news 的常驻进程每天跑一次（见 app/news.py 的 run_once）。"""
import json
from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api.v1.uploads import delete_object
from app.models import Channel, Content, DmMessage, RateHit, RoomComment, UploadObject, User, utcnow

UNSTORED_GRACE = timedelta(days=1)  # 申请了名额、一天还没传完：当作放弃
UNUSED_GRACE = timedelta(days=7)  # 传完了、七天还没用在任何地方（草稿最多也就放这么久）
CHUNK = 500

# 所有会引用上传文件 key 的字段。新增引用上传的字段时必须加到这里，否则那些文件会被当成没用上删掉。
KEY_COLUMNS = (User.avatar_key, Channel.cover_key, Content.image_key, Content.video_key, DmMessage.image_key, RoomComment.image_key)


def _used_keys(session: Session, keys: list[str]) -> set[str]:
    used: set[str] = set()
    for start in range(0, len(keys), CHUNK):
        chunk = keys[start : start + CHUNK]
        for column in KEY_COLUMNS:
            used.update(session.scalars(select(column).where(column.in_(chunk))))
    # 多图帖的图片列表存成 JSON 文本，只能整列读出来看
    # shortcut: 每天把全部多图帖的列表扫一遍；帖子到几十万条时改成单独的「帖子-文件」关联表。
    wanted = set(keys)
    for raw in session.scalars(select(Content.image_keys_json).where(Content.image_keys_json.not_in(("[]", "")))):
        used.update(key for key in json.loads(raw or "[]") if key in wanted)
    return used


def purge_unused_uploads(session: Session) -> int:
    """删掉放弃的上传名额，以及传完了却一直没用上的文件。返回删掉的文件数。"""
    now = utcnow()
    session.execute(delete(UploadObject).where(UploadObject.stored.is_(False), UploadObject.created_at < now - UNSTORED_GRACE))
    session.commit()
    stale = list(
        session.scalars(select(UploadObject.key).where(UploadObject.stored.is_(True), UploadObject.created_at < now - UNUSED_GRACE))
    )
    used = _used_keys(session, stale) if stale else set()
    unused = [key for key in stale if key not in used]
    for key in unused:
        delete_object(key)  # 先删文件再删记录：删文件失败时记录还在，第二天再试
        session.execute(delete(UploadObject).where(UploadObject.key == key))
        session.commit()
    return len(unused)


def run_housekeeping(session: Session) -> dict[str, int]:
    removed = purge_unused_uploads(session)
    session.execute(delete(RateHit).where(RateHit.at < utcnow() - timedelta(days=1)))  # 限流窗口最长一小时
    session.commit()
    return {"unused_uploads_removed": removed}
