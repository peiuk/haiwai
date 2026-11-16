"""Server-side visibility rules shared by content endpoints."""

from sqlalchemy import and_, exists, or_, select
from sqlalchemy.orm import Session, aliased

from app.core.errors import APIError
from app.models import Channel, ChannelCollaborator, ChannelItem, ChannelSubscription, Content, User, UserBlock


def can_view_content(session: Session, content: Content, user: User | None) -> bool:
    """A private room's content stays private even when addressed by content ID."""
    private_rooms = session.scalars(
        select(Channel)
        .join(ChannelItem, ChannelItem.channel_id == Channel.id)
        .where(
            ChannelItem.content_id == content.id,
            Channel.kind == "room",
            Channel.is_private.is_(True),
        )
    ).all()
    for room in private_rooms:
        if not is_room_member(session, room, user):
            return False
    if content.repost_of_id:
        # 原帖被下架 / 删除后，转发里抄下来的标题和摘要也不能再露出
        original = session.get(Content, content.repost_of_id)
        if original is None or original.deleted_at is not None or original.status != "published":
            return False
        if not can_view_content(session, original, user):
            return False
    return True


def viewable(user_id: str | None):
    """can_view_content 的 SQL 版：列表接口放进 where 里一次过滤，不用每条内容再查一次库。两处规则要保持一致。"""
    not_member = [Channel.kind == "room", Channel.is_private.is_(True)]
    if user_id:
        not_member += [
            or_(Channel.owner_id.is_(None), Channel.owner_id != user_id),
            ~exists().where(ChannelCollaborator.channel_id == Channel.id, ChannelCollaborator.user_id == user_id),
            ~exists().where(ChannelSubscription.channel_id == Channel.id, ChannelSubscription.user_id == user_id),
        ]
    hidden = select(ChannelItem.content_id).join(Channel, Channel.id == ChannelItem.channel_id).where(*not_member)
    original = aliased(Content)
    live_original = select(original.id).where(
        original.status == "published", original.deleted_at.is_(None), original.id.not_in(hidden)
    )
    return and_(Content.id.not_in(hidden), or_(Content.repost_of_id.is_(None), Content.repost_of_id.in_(live_original)))


def is_room_member(session: Session, room: Channel, user: User | None) -> bool:
    """能看私密房间的人：房主、协作者、已加入的成员。各接口统一用这一条。"""
    if user is None:
        return False
    return (
        room.owner_id == user.id
        or session.get(ChannelCollaborator, (room.id, user.id)) is not None
        or session.get(ChannelSubscription, (user.id, room.id)) is not None
    )


def require_not_blocked_by(session: Session, owner_ids: list[str | None], user_id: str) -> None:
    """被帖子作者或被回复的人拉黑了，就不能在他们的帖子 / 留言下回复（不然拉黑挡不住骚扰，对方每条都收到通知）。"""
    ids = [owner for owner in owner_ids if owner and owner != user_id]
    if ids and session.scalar(select(UserBlock.user_id).where(UserBlock.user_id.in_(ids), UserBlock.target_id == user_id).limit(1)):
        raise APIError(403, "USER_BLOCKED", "对方已把你拉黑，不能回复")


def is_private_room_content(session: Session, content: Content) -> bool:
    return session.scalar(
        select(Channel.id)
        .join(ChannelItem, ChannelItem.channel_id == Channel.id)
        .where(
            ChannelItem.content_id == content.id,
            Channel.kind == "room",
            Channel.is_private.is_(True),
        )
        .limit(1)
    ) is not None
