from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.models import Channel, ChannelItem, ChannelSubscription, Content, Notification, RoomBan, RoomPostPush

ROOM_LIMIT = 20
ROOM_TYPE_LABELS = {"general": "通用", "series": "剧集", "film": "电影", "video": "视频"}
SORT_BASIS = {"general": "按时间", "series": "按集号", "film": "按片单顺序", "video": "按加入顺序"}


def episode_sort_key(season: int, episode: int) -> str:
    return f"S{season:02d}E{episode:03d}"


def film_sort_key(index: int) -> str:
    return f"F{index:04d}"


def video_sort_key(index: int) -> str:
    return f"V{index:04d}"


def notify_room_update(session: Session, channel: Channel, content: Content) -> None:
    if channel.kind != "room":
        return
    rows = session.scalars(
        select(ChannelSubscription).where(
            ChannelSubscription.channel_id == channel.id,
            ChannelSubscription.is_muted.is_(False),
        )
    ).all()
    body = f"「{channel.name_hans}」有新内容：{content.title}"[:200]
    for row in rows:
        if row.user_id == content.author_id:
            continue
        session.add(Notification(user_id=row.user_id, kind="room.update", body=body, content_id=content.id))


def require_not_banned(session: Session, room_ids: Iterable[str], user_id: str) -> None:
    """被房主移出的人在这些房间里不能发帖、留言、转发、投稿（公开房间不用加入也能发，只拦加入不够）。"""
    ids = list(room_ids)
    if ids and session.scalar(select(RoomBan.room_id).where(RoomBan.user_id == user_id, RoomBan.room_id.in_(ids)).limit(1)):
        raise APIError(403, "ROOM_BANNED", "房主已把你移出这个房间，不能在这里发言")


def drop_pushes(session: Session, content_id: str) -> None:
    pushes = session.scalars(select(RoomPostPush).where(RoomPostPush.content_id == content_id)).all()
    for push in pushes:
        item = session.get(ChannelItem, (push.channel_id, content_id))
        if item is not None and item.origin_room_id:
            session.delete(item)
        session.delete(push)
