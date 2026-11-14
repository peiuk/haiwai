"""Server-side visibility rules shared by content endpoints."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Channel, ChannelItem, ChannelSubscription, Content, User


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
        if user is None:
            return False
        if room.owner_id != user.id and session.get(ChannelSubscription, (user.id, room.id)) is None:
            return False
    if content.repost_of_id:
        original = session.get(Content, content.repost_of_id)
        if original is not None and not can_view_content(session, original, user):
            return False
    return True


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
