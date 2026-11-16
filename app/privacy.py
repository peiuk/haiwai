"""Server-side visibility rules shared by content endpoints."""

from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.orm import Session, aliased

from app.core.errors import APIError
from app.models import Channel, ChannelCollaborator, ChannelItem, ChannelSubscription, Content, User, UserBlock


def can_view_content(session: Session, content: Content, user: User | None) -> bool:
    """私密房间的内容只给成员看；房间被下架 / 停用后，里面的内容只给房主和协作者看。按 id 打开也一样。"""
    rooms = session.scalars(
        select(Channel)
        .join(ChannelItem, ChannelItem.channel_id == Channel.id)
        .where(
            ChannelItem.content_id == content.id,
            Channel.kind == "room",
            or_(Channel.is_private.is_(True), Channel.is_active.is_(False)),
        )
    ).all()
    for room in rooms:
        if not room.is_active and not is_room_editor(session, room, user):
            return False
        if room.is_private and not is_room_member(session, room, user):
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
    private = Channel.is_private.is_(True)
    closed = Channel.is_active.is_(False)  # 被下架 / 停用（含审核中）的房间
    if user_id:
        # coalesce：owner_id 为空时比较结果是 NULL，取反后整行不算隐藏，会把内容漏出去
        editor = or_(
            func.coalesce(Channel.owner_id, "") == user_id,
            exists().where(ChannelCollaborator.channel_id == Channel.id, ChannelCollaborator.user_id == user_id),
        )
        member = or_(editor, exists().where(ChannelSubscription.channel_id == Channel.id, ChannelSubscription.user_id == user_id))
        blocked = or_(and_(private, ~member), and_(closed, ~editor))
    else:
        blocked = or_(private, closed)
    hidden = select(ChannelItem.content_id).join(Channel, Channel.id == ChannelItem.channel_id).where(Channel.kind == "room", blocked)
    original = aliased(Content)
    live_original = select(original.id).where(
        original.status == "published", original.deleted_at.is_(None), original.id.not_in(hidden)
    )
    return and_(Content.id.not_in(hidden), or_(Content.repost_of_id.is_(None), Content.repost_of_id.in_(live_original)))


def is_room_editor(session: Session, room: Channel, user: User | None) -> bool:
    """房主或协作者。"""
    if user is None:
        return False
    return room.owner_id == user.id or session.get(ChannelCollaborator, (room.id, user.id)) is not None


def is_room_member(session: Session, room: Channel, user: User | None) -> bool:
    """能看私密房间的人：房主、协作者、已加入的成员。各接口统一用这一条。"""
    return is_room_editor(session, room, user) or (
        user is not None and session.get(ChannelSubscription, (user.id, room.id)) is not None
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
