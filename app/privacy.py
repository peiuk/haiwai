"""Server-side visibility rules shared by content endpoints."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Channel, ChannelCollaborator, ChannelItem, ChannelSubscription, Content, User


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
        original = session.get(Content, content.repost_of_id)
        if original is not None and not can_view_content(session, original, user):
            return False
    return True


def is_room_member(session: Session, room: Channel, user: User | None) -> bool:
    """能看私密房间的人：房主、协作者、已加入的成员。各接口统一用这一条。"""
    if user is None:
        return False
    return (
        room.owner_id == user.id
        or session.get(ChannelCollaborator, (room.id, user.id)) is not None
        or session.get(ChannelSubscription, (user.id, room.id)) is not None
    )


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
