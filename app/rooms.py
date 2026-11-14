from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Channel, ChannelItem, ChannelSubscription, Content, Notification, RoomPostPush

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


def drop_pushes(session: Session, content_id: str) -> None:
    pushes = session.scalars(select(RoomPostPush).where(RoomPostPush.content_id == content_id)).all()
    for push in pushes:
        item = session.get(ChannelItem, (push.channel_id, content_id))
        if item is not None and item.origin_room_id:
            session.delete(item)
        session.delete(push)
