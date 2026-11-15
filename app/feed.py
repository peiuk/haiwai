import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.pagination import decode_cursor, encode_cursor
from app.keywords import load_keywords
from app.models import Channel, ChannelItem, ChannelSubscription, Content, ContentReaction, ListingExt, User
from app.privacy import can_view_content

MAX_LISTING_IMAGES = 4


def image_keys_of(content: Content) -> list[str]:
    """返回规范化后的图片 key 列表：去重、去空、最多 4 张，并兼容只有单列 image_key 的旧数据。"""
    raw = getattr(content, "image_keys_json", None) or "[]"
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        parsed = []
    keys = parsed if isinstance(parsed, list) else []
    keys = [key for key in keys if isinstance(key, str) and key]
    if not keys and content.image_key:
        keys = [content.image_key]
    unique: list[str] = []
    for key in keys:
        if key not in unique:
            unique.append(key)
    return unique[:MAX_LISTING_IMAGES]


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def listing_map(session: Session, content_ids: list[str]) -> dict[str, ListingExt]:
    if not content_ids:
        return {}
    rows = session.scalars(select(ListingExt).where(ListingExt.content_id.in_(content_ids))).all()
    return {row.content_id: row for row in rows}


def author_names(session: Session, author_ids: list[str | None]) -> dict[str, tuple[str, str, str]]:
    ids = [item for item in author_ids if item]
    if not ids:
        return {}
    rows = session.scalars(select(User).where(User.id.in_(ids))).all()
    return {row.id: (row.display_name, row.handle or "", row.avatar_key or "") for row in rows}


def repost_context(session: Session, user_id: str | None, contents: list[Content]) -> tuple[dict[str, str], set[str]]:
    original_ids = [content.repost_of_id for content in contents if content.repost_of_id]
    titles: dict[str, str] = {}
    if original_ids:
        rows = session.scalars(select(Content).where(Content.id.in_(original_ids))).all()
        titles = {row.id: row.title for row in rows}
    mine: set[str] = set()
    if user_id:
        ids = [content.id for content in contents]
        if ids:
            forwarded = session.scalars(
                select(Content.repost_of_id).where(
                    Content.author_id == user_id,
                    Content.repost_of_id.in_(ids),
                    Content.deleted_at.is_(None),
                    Content.status == "published",
                )
            ).all()
            mine = {item for item in forwarded if item}
    return titles, mine


def reaction_flags(session: Session, user_id: str | None, content_ids: list[str]) -> dict[str, tuple[bool, bool]]:
    if not user_id or not content_ids:
        return {}
    rows = session.scalars(
        select(ContentReaction).where(
            ContentReaction.user_id == user_id,
            ContentReaction.content_id.in_(content_ids),
        )
    ).all()
    return {row.content_id: (row.liked, row.favorited) for row in rows}


def _expired(expires_at: datetime | None) -> bool:
    if expires_at is None:
        return False
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at < datetime.now(timezone.utc)


def card_extras(content: Content, listing: ListingExt | None, author: tuple[str, ...] = ("", "")) -> dict[str, object]:
    author_name, author_handle, author_avatar = (*author, "")[:3]  # 调用方的缺省值是两项的 ("", "")
    extra: dict[str, object] = {
        "type": content.type,
        "keywords": load_keywords(content.keywords_json),
        "image_key": content.image_key,
        "image_keys": image_keys_of(content),
        "video_key": content.video_key,
        "rights_confirmed": content.rights_confirmed,
        "author_id": content.author_id,
        "author_name": author_name,
        "author_handle": author_handle,
        "author_avatar": author_avatar,
        "city_topic": content.city_topic or "",
        "keyword_source": content.keyword_source or "",
    }
    if listing is not None:
        extra["listing"] = {
            "category": listing.category,
            "kind": listing.kind,
            "area": listing.area,
            "price_amount": listing.price_amount,
            "price_unit": listing.price_unit or "",
            "currency": listing.currency,
            "closed_reason": listing.closed_reason,
            "certified": content.status == "published",
            "expires_at": content.expires_at.isoformat() if content.expires_at else None,
            "expired": _expired(content.expires_at),
        }
    return extra


def content_titles(content: Content) -> tuple[str, str, str | None, str | None]:
    title_hans = content.title
    title_hant = content.title_hant or content.title
    summary_hans = content.summary
    summary_hant = content.summary_hant or content.summary
    return title_hans, title_hant, summary_hans, summary_hant


def build_following_feed(session: Session, user_id: str) -> list[dict[str, object]]:
    subscriptions = {
        row.channel_id: row
        for row in session.scalars(select(ChannelSubscription).where(ChannelSubscription.user_id == user_id)).all()
    }
    rows = session.scalars(
        select(ChannelItem)
        .join(
            ChannelSubscription,
            (ChannelSubscription.channel_id == ChannelItem.channel_id)
            & (ChannelSubscription.user_id == user_id)
            & (ChannelSubscription.is_muted.is_(False)),
        )
        .join(Content, Content.id == ChannelItem.content_id)
        .where(Content.status == "published", Content.deleted_at.is_(None))
        .options(joinedload(ChannelItem.channel), joinedload(ChannelItem.content))
        .order_by(ChannelItem.pinned.desc(), ChannelItem.added_at.desc())
    ).unique().all()
    viewer = session.get(User, user_id)
    rows = [item for item in rows if can_view_content(session, item.content, viewer)]

    ordered: list[str] = []
    grouped: dict[str, dict[str, object]] = {}
    unread_context: dict[str, list[tuple[datetime, str]]] = {}
    listings = listing_map(session, [item.content_id for item in rows if item.content.type == "listing"])
    authors = author_names(session, [item.content.author_id for item in rows])
    repost_titles, reposted_ids = repost_context(session, user_id, [item.content for item in rows])

    for item in rows:
        key = item.content.event_cluster_id or item.content_id
        entry = grouped.get(key)
        if entry is None:
            ordered.append(key)
            title_hans, title_hant, summary_hans, summary_hant = content_titles(item.content)
            entry = {
                "content_id": item.content_id,
                "event_cluster_id": item.content.event_cluster_id,
                "title": title_hans,
                "title_hant": title_hant,
                "summary": summary_hans,
                "summary_hant": summary_hant,
                "channels": [],
                "channel_id": item.channel_id,
                "channel_name": item.channel.name_hans,
                "channel_certified": item.channel.certified,
                "is_joined": True,
                "source_name": item.content.source_name or "",
                "licence_ref": item.content.licence_ref or "",
                "canonical_url": item.content.canonical_url,
                "added_at": item.added_at.isoformat(),
                "pinned": item.pinned,
                "sources": [],
                "source_count": 1,
                "source_label": None,
                "origin_room_name": None,
                "embed_status": item.content.embed_status,
                "embed_provider_code": item.content.embed_provider_code,
                **card_extras(item.content, listings.get(item.content_id), authors.get(item.content.author_id or "", ("", ""))),
                "reposted": item.content_id in reposted_ids,
                "repost_of": (
                    {"content_id": item.content.repost_of_id, "title": repost_titles.get(item.content.repost_of_id, "")}
                    if item.content.repost_of_id
                    else None
                ),
            }
            grouped[key] = entry
            unread_context[key] = []
        channels = entry["channels"]
        if isinstance(channels, list) and item.channel.code not in channels:
            channels.append(item.channel.code)
        if item.channel.kind == "room":
            entry["source_label"] = "joined_room"
            entry["origin_room_name"] = item.channel.name_hans
        elif item.origin_room_id and entry.get("source_label") is None:
            entry["source_label"] = "pushed_room"
            room = session.get(Channel, item.origin_room_id)
            entry["origin_room_name"] = room.name_hans if room else ""
        unread_context[key].append((item.added_at, item.channel_id))
        sources = entry["sources"]
        url = item.content.canonical_url
        if isinstance(sources, list) and url and all(source.get("canonical_url") != url for source in sources):
            sources.append(
                {
                    "canonical_url": url,
                    "title": item.content.title,
                    "source_name": item.content.source_name or "",
                }
            )
            entry["source_count"] = len(sources)

    last_read = {channel_id: sub.last_read_at for channel_id, sub in subscriptions.items()}
    flags = reaction_flags(session, user_id, [str(entry["content_id"]) for entry in grouped.values()])
    items: list[dict[str, object]] = []
    for key in ordered:
        entry = dict(grouped[key])
        liked, favorited = flags.get(str(entry["content_id"]), (False, False))
        entry["liked"] = liked
        entry["favorited"] = favorited
        is_unread = False
        for added_at, channel_id in unread_context.get(key, []):
            read_at = last_read.get(channel_id)
            if read_at is None or _aware(added_at) > _aware(read_at):
                is_unread = True
                break
        entry["is_unread"] = is_unread
        items.append(entry)
    return items


def paginate_feed(
    items: list[dict[str, object]],
    cursor: str | None,
    limit: int,
) -> tuple[list[dict[str, object]], str | None]:
    start = 0
    if cursor:
        parts = decode_cursor(cursor)
        if parts and len(parts) == 2:
            cursor_id, cursor_at = parts[0], parts[1]
            for index, item in enumerate(items):
                if item["content_id"] == cursor_id and item.get("added_at") == cursor_at:
                    start = index + 1
                    break
    page = items[start : start + limit]
    next_cursor = None
    if start + limit < len(items) and page:
        last = page[-1]
        next_cursor = encode_cursor(str(last["content_id"]), str(last["added_at"]))
    return page, next_cursor
