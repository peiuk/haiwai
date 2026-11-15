from fastapi import APIRouter, Depends
from pydantic import BaseModel, field_validator
from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.api.v1.auth import current_user, optional_user, require_verified_phone
from app.core.pagination import decode_cursor, encode_cursor
from app.feed import author_names, card_extras, content_titles, listing_map, reaction_flags, repost_context
from app.recommend import country_blocked, effective_region
from app.reports import ReportBody, report_receipt
from app.core.audit import write_audit
from app.core.db import get_db
from app.core.errors import APIError
from app.models import (
    Channel,
    ChannelCollaborator,
    ChannelItem,
    ChannelSubscription,
    Content,
    ModerationCase,
    RoomComment,
    RoomPostPush,
    RoomJoinRequest,
    User,
    UserItemProgress,
    new_id,
    utcnow,
)
from app.privacy import can_view_content, is_room_member
from app.rooms import (
    ROOM_LIMIT,
    ROOM_TYPE_LABELS,
    SORT_BASIS,
    drop_pushes,
    episode_sort_key,
    film_sort_key,
    notify_room_update,
    video_sort_key,
)

router = APIRouter(prefix="/channels")


@router.get("")
def list_channels(
    region_code: str | None = None,
    kind: str | None = None,
    q: str | None = None,
    session: Session = Depends(get_db),
) -> dict[str, list[dict[str, object]]]:
    has_published = exists(
        select(ChannelItem.channel_id)
        .join(Content, Content.id == ChannelItem.content_id)
        .where(
            ChannelItem.channel_id == Channel.id,
            Content.status == "published",
            Content.deleted_at.is_(None),
        )
    )
    query = select(Channel).where(
        Channel.is_active.is_(True),
        Channel.visibility == "public",
        Channel.is_private.is_(False),
        or_(Channel.kind != "room", has_published),
    )
    if region_code:
        query = query.where(Channel.region_code == region_code.strip().upper())
    if kind:
        query = query.where(Channel.kind == kind.strip())
    if q:
        needle = f"%{q.strip()}%"
        query = query.where(Channel.name_hans.ilike(needle) | Channel.code.ilike(needle))
    rows = session.scalars(query.order_by(Channel.sort_order, Channel.code)).all()
    return {
        "items": [
            {
                "id": row.id,
                "code": row.code,
                "name_hans": row.name_hans,
                "name_hant": row.name_hant,
                "kind": row.kind,
                "room_type": row.room_type,
                "certified": row.certified,
                "region_code": row.region_code,
                "parent_channel_id": row.parent_channel_id,
                "subscriber_count": row.subscriber_count,
                "category": row.category,
            }
            for row in rows
        ]
    }


@router.get("/recommended")
def recommended_channels(
    user: User | None = Depends(optional_user),
    session: Session = Depends(get_db),
) -> dict[str, list[dict[str, object]]]:
    region = effective_region(session, user) if user is not None else "GLOBAL"
    joined: set[str] = set()
    if user is not None:
        joined = set(
            session.scalars(select(ChannelSubscription.channel_id).where(ChannelSubscription.user_id == user.id)).all()
        )
    rows = session.scalars(
        select(Channel)
        .where(Channel.is_active.is_(True), Channel.visibility == "public", Channel.kind != "room")
        .order_by(Channel.subscriber_count.desc())
    ).all()
    items = [
        {"id": row.id, "code": row.code, "name_hans": row.name_hans, "region_code": row.region_code}
        for row in rows
        if row.id not in joined and (row.region_code == "GLOBAL" or row.region_code == region)
    ][:3]
    return {"items": items}


def _channel_rooms(session: Session, channel: Channel, user: User | None) -> list[dict[str, object]]:
    rows = session.scalars(
        select(Channel)
        .where(
            Channel.parent_channel_id == channel.id,
            Channel.kind == "room",
            Channel.visibility == "public",
        )
        .order_by(Channel.name_hans)
    ).all()
    published_ids = set(
        session.scalars(
            select(ChannelItem.channel_id)
            .join(Content, Content.id == ChannelItem.content_id)
            .where(
                ChannelItem.channel_id.in_([row.id for row in rows] or [""]),
                Content.status == "published",
                Content.deleted_at.is_(None),
            )
            .distinct()
        ).all()
    )
    rooms: list[dict[str, object]] = []
    for row in rows:
        owns = user is not None and row.owner_id == user.id
        public = row.is_active and not row.is_private and row.id in published_ids
        if not owns and not public:
            continue
        rooms.append(
            {
                "id": row.id,
                "name_hans": row.name_hans,
                "room_type": row.room_type,
                "is_private": row.is_private,
                "is_active": row.is_active,
                "has_published": row.id in published_ids,
            }
        )
    return rooms


def _open_channel(session: Session, channel: Channel | None, user: User | None) -> Channel:
    if channel is None or channel.visibility != "public":
        raise APIError(404, "CHANNEL_NOT_FOUND", "频道不存在")
    if channel.is_active:
        return channel
    if user is not None and channel.kind == "room" and (
        channel.owner_id == user.id or session.get(ChannelCollaborator, (channel.id, user.id)) is not None
    ):
        return channel
    raise APIError(404, "CHANNEL_NOT_FOUND", "频道不存在")


@router.get("/{channel_id}")
def channel_detail(
    channel_id: str,
    user: User | None = Depends(optional_user),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    channel = _open_channel(session, session.get(Channel, channel_id), user)
    joined = False
    if user is not None:
        joined = session.get(ChannelSubscription, (user.id, channel.id)) is not None
    if channel.kind == "room" and channel.is_private and not is_room_member(session, channel, user):
        pending = user is not None and session.scalar(
            select(RoomJoinRequest.id).where(RoomJoinRequest.room_id == channel.id, RoomJoinRequest.user_id == user.id)
        ) is not None
        return {
            "id": channel.id,
            "code": channel.code,
            "name_hans": channel.name_hans,
            "name_hant": channel.name_hant,
            "kind": channel.kind,
            "room_type": channel.room_type,
            "is_private": True,
            "is_joined": False,
            "join_request_pending": pending,
            "region_blocked": country_blocked(session, user, channel),
            "parent_channel_id": channel.parent_channel_id,
        }
    parent = session.get(Channel, channel.parent_channel_id) if channel.parent_channel_id else None
    if country_blocked(session, user, channel):
        return {
            "id": channel.id,
            "code": channel.code,
            "name_hans": channel.name_hans,
            "name_hant": channel.name_hant,
            "kind": channel.kind,
            "room_type": channel.room_type,
            "region_code": channel.region_code,
            "region_blocked": True,
            "is_joined": joined,
            "parent_channel_id": channel.parent_channel_id,
            "parent_name_hans": parent.name_hans if parent is not None else "",
            "owner": _member(session, channel.owner_id, "owner"),
            "seasons": [],
            "rooms": [],
        }
    pinned = session.scalar(
        select(func.count())
        .select_from(ChannelItem)
        .join(Content, Content.id == ChannelItem.content_id)
        .where(
            ChannelItem.channel_id == channel.id,
            ChannelItem.pinned.is_(True),
            Content.status == "published",
            Content.deleted_at.is_(None),
        )
    )
    return {
        "id": channel.id,
        "code": channel.code,
        "name_hans": channel.name_hans,
        "name_hant": channel.name_hant,
        "kind": channel.kind,
        "room_type": channel.room_type,
        "room_type_label": ROOM_TYPE_LABELS.get(channel.room_type, channel.room_type),
        "review_status": channel.review_status,
        "is_private": channel.is_private,
        "is_owner": user is not None and channel.owner_id == user.id,
        "sort_basis": SORT_BASIS.get(channel.room_type, "按时间") if channel.kind == "room" else "",
        "certified": channel.certified,
        "region_code": channel.region_code,
        "category": parent.category if channel.kind == "room" and parent is not None else channel.category,
        "parent_channel_id": channel.parent_channel_id,
        "parent_name_hans": parent.name_hans if parent is not None else "",
        "subscriber_count": channel.subscriber_count,
        "is_joined": joined,
        "region_blocked": False,
        "pinned_announcement_count": int(pinned or 0),
        "seasons": [
            item
            for item in session.scalars(
                select(ChannelItem.season)
                .join(Content, Content.id == ChannelItem.content_id)
                .where(
                    ChannelItem.channel_id == channel.id,
                    ChannelItem.season.is_not(None),
                    Content.status == "published",
                    Content.deleted_at.is_(None),
                )
                .distinct()
                .order_by(ChannelItem.season)
            ).all()
            if item is not None
        ],
        "owner": _member(session, channel.owner_id, "owner"),
        "collaborators": [
            _member(session, row.user_id, "collaborator")
            for row in session.scalars(
                select(ChannelCollaborator).where(ChannelCollaborator.channel_id == channel.id)
            ).all()
        ],
        "rooms": _channel_rooms(session, channel, user),
    }


@router.get("/{channel_id}/items")
def channel_items(
    channel_id: str,
    cursor: str | None = None,
    limit: int = 20,
    season: int | None = None,
    user: User | None = Depends(optional_user),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    channel = _open_channel(session, session.get(Channel, channel_id), user)
    if channel.is_private and not is_room_member(session, channel, user):
        raise APIError(404, "CHANNEL_NOT_FOUND", "频道不存在")
    if country_blocked(session, user, channel):
        return {"items": [], "region_blocked": True}
    visible = Content.status == "published"
    if user is not None:
        visible = or_(Content.status == "published", and_(Content.status == "pending", Content.author_id == user.id))
    rows = session.scalars(
        select(ChannelItem)
        .join(Content, Content.id == ChannelItem.content_id)
        .where(
            ChannelItem.channel_id == channel.id,
            visible,
            Content.deleted_at.is_(None),
            *([ChannelItem.season == season] if season is not None else []),
        )
        .options(joinedload(ChannelItem.content))
        .order_by(
            ChannelItem.pinned.desc(),
            ChannelItem.sort_key.asc() if channel.room_type in {"series", "film", "video"} else ChannelItem.added_at.desc(),
            ChannelItem.added_at.asc() if channel.room_type in {"series", "film", "video"} else ChannelItem.added_at.desc(),
        )
    ).unique().all()
    rows = [row for row in rows if can_view_content(session, row.content, user)]
    bounded = min(max(limit, 1), 50)
    start = 0
    if cursor:
        parts = decode_cursor(cursor)
        if parts and len(parts) == 2:
            cursor_id, cursor_at = parts[0], parts[1]
            for index, row in enumerate(rows):
                if row.content_id == cursor_id and row.added_at.isoformat() == cursor_at:
                    start = index + 1
                    break
    page_rows = rows[start : start + bounded]
    listings = listing_map(session, [row.content_id for row in page_rows if row.content.type == "listing"])
    authors = author_names(session, [row.content.author_id for row in page_rows])
    flags = reaction_flags(session, user.id if user else None, [row.content_id for row in page_rows])
    comment_counts = {
        content_id: count
        for content_id, count in session.execute(
            select(RoomComment.content_id, func.count())
            .where(
                RoomComment.content_id.in_([row.content_id for row in page_rows] or [""]),
                RoomComment.status == "published",
                RoomComment.removed_at.is_(None),
            )
            .group_by(RoomComment.content_id)
        ).all()
    }
    repost_titles, reposted_ids = repost_context(session, user.id if user else None, [row.content for row in page_rows])
    progress: dict[str, int] = {}
    if user is not None and page_rows:
        marks = session.scalars(
            select(UserItemProgress).where(
                UserItemProgress.user_id == user.id,
                UserItemProgress.content_id.in_([row.content_id for row in page_rows]),
            )
        ).all()
        progress = {mark.content_id: mark.progress for mark in marks}
        watch_marks = {mark.content_id: mark.watch_mark or None for mark in marks}
    room_ids = [row.origin_room_id for row in page_rows if row.origin_room_id]
    room_names = {
        room.id: room.name_hans
        for room in session.scalars(select(Channel).where(Channel.id.in_(room_ids or [""]))).all()
    }
    items: list[dict[str, object]] = []
    for row in page_rows:
        title_hans, title_hant, summary_hans, summary_hant = content_titles(row.content)
        items.append(
            {
                "content_id": row.content_id,
                "title": title_hans,
                "title_hant": title_hant,
                "summary": summary_hans,
                "summary_hant": summary_hant,
                "source_name": row.content.source_name or "",
                "licence_ref": row.content.licence_ref or "",
                "canonical_url": row.content.canonical_url,
                "embed_status": row.content.embed_status,
                "embed_provider_code": row.content.embed_provider_code,
                "origin_room_id": row.origin_room_id,
                "origin_room_name": room_names.get(row.origin_room_id) if row.origin_room_id else None,
                **card_extras(row.content, listings.get(row.content_id), authors.get(row.content.author_id or "", ("", ""))),
                "liked": flags.get(row.content_id, (False, False))[0],
                "favorited": flags.get(row.content_id, (False, False))[1],
                "reposted": row.content_id in reposted_ids,
                "repost_of": (
                    {"content_id": row.content.repost_of_id, "title": repost_titles.get(row.content.repost_of_id, "")}
                    if row.content.repost_of_id
                    else None
                ),
                "status": row.content.status,
                "comment_count": int(comment_counts.get(row.content_id, 0)),
                "pinned": row.pinned,
                "season": row.season,
                "episode": row.episode,
                "year": row.year,
                "sort_key": row.sort_key or "",
                "rights_confirmed": row.rights_confirmed,
                "progress": progress.get(row.content_id),
                "watch_mark": watch_marks.get(row.content_id) if user is not None else None,
                "added_at": row.added_at.isoformat(),
            }
        )
    payload: dict[str, object] = {
        "items": items,
        "progress_scope": "self",
        "sort_basis": SORT_BASIS.get(channel.room_type, "按时间") if channel.kind == "room" else "按时间",
    }
    if start + bounded < len(rows) and page_rows:
        last = page_rows[-1]
        payload["next_cursor"] = encode_cursor(last.content_id, last.added_at.isoformat())
    return payload


@router.post("/{channel_id}/read")
def mark_channel_read(
    channel_id: str,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, int]:
    subscription = session.get(ChannelSubscription, (user.id, channel_id))
    if subscription is None:
        raise APIError(404, "SUBSCRIPTION_NOT_FOUND", "还没有加入这个频道")
    subscription.last_read_at = utcnow()
    subscription.unread_count = 0
    session.commit()
    return {"unread_count": 0}


_ROOM_TYPES = {"general", "series", "film", "video"}


class RoomBody(BaseModel):
    name: str
    parent_channel_id: str
    is_private: bool = False
    room_type: str = "general"

    @field_validator("room_type")
    @classmethod
    def known_room_type(cls, value: str) -> str:
        if value not in _ROOM_TYPES:
            raise ValueError("房间类型不正确")
        return value

    @field_validator("name")
    @classmethod
    def name_length(cls, value: str) -> str:
        name = value.strip()
        if not name or len(name) > 64:
            raise ValueError("房间名需要 1 到 64 个字")
        if "官方" in name:
            raise ValueError("房间名不能使用官方")
        return name


class TextBody(BaseModel):
    title: str
    body: str

    @field_validator("title")
    @classmethod
    def title_length(cls, value: str) -> str:
        title = value.strip()
        if not title or len(title) > 200:
            raise ValueError("标题需要 1 到 200 个字")
        return title

    @field_validator("body")
    @classmethod
    def body_length(cls, value: str) -> str:
        text = value.strip()
        if not text or len(text) > 4000:
            raise ValueError("正文需要 1 到 4000 个字")
        return text


class SubmissionDecision(BaseModel):
    decision: str

    @field_validator("decision")
    @classmethod
    def known_decision(cls, value: str) -> str:
        if value not in {"accept", "reject"}:
            raise ValueError("决定只能是接收或拒绝")
        return value


def _official_parent(session: Session, parent_id: str) -> Channel:
    parent = session.get(Channel, parent_id)
    if parent is None or not parent.is_active or not parent.kind.startswith("official"):
        raise APIError(400, "PARENT_REQUIRED", "房间必须挂在官方频道下面")
    return parent


@router.post("")
def create_room(
    body: RoomBody,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    require_verified_phone(user, "创建")
    parent = _official_parent(session, body.parent_channel_id)
    owned = session.scalar(select(func.count()).select_from(Channel).where(Channel.owner_id == user.id))
    if (owned or 0) >= ROOM_LIMIT:
        raise APIError(409, "CHANNEL_LIMIT", f"一个人最多创建 {ROOM_LIMIT} 个房间")
    channel_id = new_id()
    channel = Channel(
        id=channel_id,
        code=f"room-{channel_id[:8]}",
        name_hans=body.name,
        name_hant=body.name,
        kind="room",
        room_type=body.room_type,
        visibility="public",
        region_code=parent.region_code,
        owner_id=user.id,
        parent_channel_id=parent.id,
        is_active=False,
        is_private=body.is_private,
        review_status="pending",
    )
    session.add(channel)
    write_audit(session, user.id, "channel.create", "channel", channel.id)
    session.commit()
    return {"channel_id": channel.id, "review_status": channel.review_status, "room_type": channel.room_type}


class RoomTypeBody(BaseModel):
    room_type: str

    @field_validator("room_type")
    @classmethod
    def known_room_type(cls, value: str) -> str:
        if value not in _ROOM_TYPES:
            raise ValueError("房间类型不正确")
        return value


@router.patch("/{channel_id}")
def update_room_type(
    channel_id: str,
    body: RoomTypeBody,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    channel = _owner_channel(session, channel_id, user)
    if channel.kind != "room":
        raise APIError(404, "CHANNEL_NOT_FOUND", "频道不存在")
    channel.room_type = body.room_type
    session.commit()
    return {"channel_id": channel.id, "room_type": channel.room_type}


@router.put("/{channel_id}/collaborators/{member_id}")
def add_collaborator(
    channel_id: str,
    member_id: str,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    channel = _owner_channel(session, channel_id, user)
    if channel.kind != "room":
        raise APIError(404, "CHANNEL_NOT_FOUND", "频道不存在")
    member = session.get(User, member_id)
    if member is None or member.deleted_at is not None or member.id == channel.owner_id:
        raise APIError(404, "USER_NOT_FOUND", "用户不存在")
    if session.get(ChannelCollaborator, (channel.id, member.id)) is None:
        session.add(ChannelCollaborator(channel_id=channel.id, user_id=member.id))
        session.commit()
    return {"user_id": member.id, "role": "collaborator"}


@router.delete("/{channel_id}/collaborators/{member_id}")
def remove_collaborator(
    channel_id: str,
    member_id: str,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, bool]:
    channel = _owner_channel(session, channel_id, user)
    row = session.get(ChannelCollaborator, (channel.id, member_id))
    if row is not None:
        session.delete(row)
        session.commit()
    return {"removed": True}


class EntryBody(BaseModel):
    title: str
    body: str
    season: int | None = None
    episode: int | None = None
    year: int | None = None
    rights_confirmed: bool = False

    @field_validator("title")
    @classmethod
    def entry_title(cls, value: str) -> str:
        title = value.strip()
        if not title or len(title) > 200:
            raise ValueError("标题需要 1 到 200 个字")
        return title

    @field_validator("body")
    @classmethod
    def entry_body(cls, value: str) -> str:
        text = value.strip()
        if not text or len(text) > 4000:
            raise ValueError("正文需要 1 到 4000 个字")
        return text


class MoveBody(BaseModel):
    direction: str

    @field_validator("direction")
    @classmethod
    def known_direction(cls, value: str) -> str:
        if value not in {"up", "down"}:
            raise ValueError("只能上移或下移")
        return value


class ProgressBody(BaseModel):
    progress: int
    watch_mark: str | None = None

    @field_validator("progress")
    @classmethod
    def progress_range(cls, value: int) -> int:
        if value < 0 or value > 100:
            raise ValueError("进度需要在 0 到 100 之间")
        return value

    @field_validator("watch_mark")
    @classmethod
    def known_watch_mark(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if value not in {"want", "watched", ""}:
            raise ValueError("只能标记想看或看过")
        return value


def _member(session: Session, user_id: str | None, role: str) -> dict[str, str] | None:
    if not user_id:
        return None
    person = session.get(User, user_id)
    if person is None:
        return None
    return {
        "user_id": person.id,
        "display_name": person.display_name,
        "handle": person.handle or "",
        "avatar_tone": person.avatar_tone,
        "role": role,
    }


def _editor_channel(session: Session, channel_id: str, user: User) -> Channel:
    channel = session.get(Channel, channel_id)
    if channel is None:
        raise APIError(404, "CHANNEL_NOT_FOUND", "频道不存在")
    if channel.owner_id == user.id or session.get(ChannelCollaborator, (channel.id, user.id)) is not None:
        return channel
    raise APIError(404, "CHANNEL_NOT_FOUND", "频道不存在")


def _catalog_room(session: Session, channel_id: str, user: User) -> Channel:
    channel = _editor_channel(session, channel_id, user)
    if not channel.is_active or channel.room_type not in {"series", "film", "video"}:
        raise APIError(409, "ROOM_TYPE", "这个房间不能编排条目")
    return channel


def _catalog_rows(session: Session, channel_id: str, season: int | None = None) -> list[ChannelItem]:
    query = select(ChannelItem).where(ChannelItem.channel_id == channel_id, ChannelItem.sort_key != "")
    if season is not None:
        query = query.where(ChannelItem.season == season)
    return list(session.scalars(query.order_by(ChannelItem.sort_key)).all())


@router.post("/{channel_id}/entries")
def add_entry(
    channel_id: str,
    body: EntryBody,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    channel = _catalog_room(session, channel_id, user)
    season = body.season
    episode = body.episode
    if channel.room_type == "series":
        if season is None or episode is None or not 1 <= season <= 99 or not 1 <= episode <= 999:
            raise APIError(400, "VALIDATION_FAILED", "剧集需要季和集")
        taken = session.scalar(
            select(ChannelItem).where(
                ChannelItem.channel_id == channel.id,
                ChannelItem.season == season,
                ChannelItem.episode == episode,
            )
        )
        if taken is not None:
            raise APIError(409, "EPISODE_TAKEN", "这一集已经有了")
        sort_key = episode_sort_key(season, episode)
        confirmed = False
    elif channel.room_type == "video":
        if not body.rights_confirmed:
            raise APIError(400, "RIGHTS_REQUIRED", "原创视频需要确认人物同意，且没有未授权的音乐或影视片段")
        season = None
        episode = None
        confirmed = True
        count = session.scalar(
            select(func.count()).select_from(ChannelItem).where(ChannelItem.channel_id == channel.id, ChannelItem.sort_key != "")
        )
        sort_key = video_sort_key(int(count or 0) + 1)
    else:
        season = None
        episode = None
        count = session.scalar(
            select(func.count()).select_from(ChannelItem).where(ChannelItem.channel_id == channel.id, ChannelItem.sort_key != "")
        )
        if body.year is None or not 1888 <= body.year <= 2100:
            raise APIError(400, "VALIDATION_FAILED", "电影需要年份")
        sort_key = film_sort_key(int(count or 0) + 1)
        confirmed = False
    now = utcnow()
    content = Content(
        type="post",
        status="published",
        author_id=user.id,
        title=body.title,
        summary=body.body[:500],
        body=body.body,
        source_name=user.display_name,
        published_at=now,
    )
    session.add(content)
    session.flush()
    session.add(
        ChannelItem(
            channel_id=channel.id,
            content_id=content.id,
            sort_key=sort_key,
            season=season,
            episode=episode,
            year=body.year if channel.room_type == "film" else None,
            rights_confirmed=confirmed,
            added_at=now,
        )
    )
    notify_room_update(session, channel, content)
    session.commit()
    return {"content_id": content.id, "sort_key": sort_key}


@router.post("/{channel_id}/entries/{content_id}/move")
def move_entry(
    channel_id: str,
    content_id: str,
    body: MoveBody,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    channel = _catalog_room(session, channel_id, user)
    item = session.get(ChannelItem, (channel.id, content_id))
    if item is None or not item.sort_key:
        raise APIError(404, "CONTENT_NOT_FOUND", "条目不存在")
    rows = _catalog_rows(session, channel.id, item.season if channel.room_type == "series" else None)
    index = next((pos for pos, row in enumerate(rows) if row.content_id == item.content_id), -1)
    neighbor_index = index - 1 if body.direction == "up" else index + 1
    if index < 0 or neighbor_index < 0 or neighbor_index >= len(rows):
        raise APIError(409, "SORT_EDGE", "已经到头了")
    neighbor = rows[neighbor_index]
    item.sort_key, neighbor.sort_key = neighbor.sort_key, item.sort_key
    session.commit()
    return {"content_id": item.content_id, "sort_key": item.sort_key}


@router.post("/{channel_id}/entries/reorder")
def reorder_entries(
    channel_id: str,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, int]:
    channel = _catalog_room(session, channel_id, user)
    if channel.room_type != "series":
        raise APIError(409, "ROOM_TYPE", "只有剧集可以按集号重排")
    rows = _catalog_rows(session, channel.id)
    for row in rows:
        if row.season is None or row.episode is None:
            continue
        row.sort_key = episode_sort_key(row.season, row.episode)
    session.commit()
    return {"reordered": len(rows)}


@router.put("/{channel_id}/items/{content_id}/progress")
def save_progress(
    channel_id: str,
    content_id: str,
    body: ProgressBody,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    channel = session.get(Channel, channel_id)
    if channel is None or not channel.is_active:
        raise APIError(404, "CHANNEL_NOT_FOUND", "频道不存在")
    if channel.is_private and not is_room_member(session, channel, user):
        raise APIError(404, "CHANNEL_NOT_FOUND", "频道不存在")
    item = session.get(ChannelItem, (channel.id, content_id))
    if item is None:
        raise APIError(404, "CONTENT_NOT_FOUND", "条目不存在")
    mark = session.get(UserItemProgress, (user.id, content_id))
    if mark is None:
        mark = UserItemProgress(
            user_id=user.id,
            content_id=content_id,
            progress=body.progress,
            watch_mark=body.watch_mark or "",
            updated_at=utcnow(),
        )
        session.add(mark)
    else:
        mark.progress = body.progress
        if body.watch_mark is not None:
            mark.watch_mark = body.watch_mark
        mark.updated_at = utcnow()
    session.commit()
    return {"progress": mark.progress, "watch_mark": mark.watch_mark or None}


def _owner_channel(session: Session, channel_id: str, user: User) -> Channel:
    channel = session.get(Channel, channel_id)
    if channel is None or channel.owner_id != user.id:
        raise APIError(404, "CHANNEL_NOT_FOUND", "频道不存在")
    return channel


@router.post("/{channel_id}/report")
def report_room(
    channel_id: str,
    body: ReportBody,
    user: User | None = Depends(optional_user),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    channel = session.get(Channel, channel_id)
    if channel is None or not channel.is_active or channel.visibility != "public":
        raise APIError(404, "CHANNEL_NOT_FOUND", "频道不存在")
    if channel.is_private and not is_room_member(session, channel, user):
        raise APIError(404, "CHANNEL_NOT_FOUND", "频道不存在")
    if user is not None and channel.owner_id == user.id:
        raise APIError(403, "SELF_REPORT", "不能举报自己的房间")
    if user is not None:
        existing = session.scalar(
            select(ModerationCase.id).where(
                ModerationCase.reported_channel_id == channel.id,
                ModerationCase.reporter_id == user.id,
            )
        )
        if existing:
            raise APIError(409, "DUPLICATE_REPORT", "你已经举报过这个房间")
    case = ModerationCase(
        reported_channel_id=channel.id,
        reporter_id=user.id if user else None,
        reason=body.reason,
        detail=body.detail,
    )
    session.add(case)
    session.flush()
    write_audit(session, user.id if user else None, "channel.report", "channel", channel.id)
    session.commit()
    return report_receipt(case)


@router.post("/{channel_id}/announcements")
def create_announcement(
    channel_id: str,
    body: TextBody,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    channel = _editor_channel(session, channel_id, user)
    if country_blocked(session, user, channel):
        raise APIError(403, "REGION_BLOCKED", "当前国家看不到这个频道")
    now = utcnow()
    waiting = not channel.is_active
    content = Content(
        type="announcement",
        status="pending" if waiting else "published",
        author_id=user.id,
        title=body.title,
        summary=body.body[:500],
        body=body.body,
        source_name=user.display_name,
        published_at=None if waiting else now,
    )
    session.add(content)
    session.flush()
    session.add(ChannelItem(channel_id=channel.id, content_id=content.id, pinned=not waiting, added_at=now))
    if not waiting:
        notify_room_update(session, channel, content)
    write_audit(session, user.id, "announcement.create", "content", content.id)
    session.commit()
    return {"content_id": content.id, "status": content.status}


@router.get("/{channel_id}/submissions")
def list_submissions(
    channel_id: str,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    """房主 / 协作者查看待审投稿队列（status=pending）。

    普通投稿者在 items 里只能看到「自己投稿的 pending」，看不到他人投稿；
    房主需要这里拿到完整待审列表以便裁决 accept/reject。
    """
    channel = _editor_channel(session, channel_id, user)
    rows = session.scalars(
        select(ChannelItem)
        .join(Content, Content.id == ChannelItem.content_id)
        .where(
            ChannelItem.channel_id == channel.id,
            Content.status == "pending",
            Content.deleted_at.is_(None),
        )
        .order_by(ChannelItem.added_at.desc())
    ).all()
    items: list[dict[str, object]] = []
    for row in rows:
        content = row.content
        author = session.get(User, content.author_id)
        items.append(
            {
                "content_id": content.id,
                "title": content.title,
                "summary": content.summary,
                "author_id": content.author_id,
                "author_name": author.display_name if author else "",
                "author_handle": author.handle or "" if author else "",
                "created_at": content.created_at.isoformat() if content.created_at else row.added_at.isoformat(),
            }
        )
    return {"items": items, "pending_count": len(items)}


@router.post("/{channel_id}/submissions")
def create_submission(
    channel_id: str,
    body: TextBody,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    require_verified_phone(user, "投稿")
    channel = session.get(Channel, channel_id)
    if channel is None or not channel.is_active or channel.visibility != "public":
        raise APIError(404, "CHANNEL_NOT_FOUND", "频道不存在")
    if channel.kind == "room" and channel.is_private and not is_room_member(session, channel, user):
        raise APIError(403, "ROOM_PRIVATE", "加入私密房间后才能投稿")
    if country_blocked(session, user, channel):
        raise APIError(403, "REGION_BLOCKED", "当前国家看不到这个频道")
    now = utcnow()
    content = Content(
        type="post",
        status="pending",
        author_id=user.id,
        title=body.title,
        summary=body.body[:500],
        body=body.body,
        source_name=user.display_name,
    )
    session.add(content)
    session.flush()
    session.add(ChannelItem(channel_id=channel.id, content_id=content.id, pinned=False, added_at=now))
    write_audit(session, user.id, "submission.create", "content", content.id)
    session.commit()
    return {"content_id": content.id, "status": content.status}


@router.post("/{channel_id}/submissions/{content_id}/decision")
def decide_submission(
    channel_id: str,
    content_id: str,
    body: SubmissionDecision,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    channel = _editor_channel(session, channel_id, user)
    if not channel.is_active:
        raise APIError(403, "CHANNEL_PENDING", "频道还在审核")
    content = session.get(Content, content_id)
    item = session.get(ChannelItem, (channel.id, content_id))
    if content is None or item is None or content.deleted_at is not None:
        raise APIError(404, "CONTENT_NOT_FOUND", "投稿不存在")
    if content.status != "pending":
        raise APIError(409, "CONTENT_ALREADY_DECIDED", "这条投稿已经处理过")
    now = utcnow()
    if body.decision == "accept":
        content.status = "published"
        content.published_at = now
        item.added_at = now
        notify_room_update(session, channel, content)
        write_audit(session, user.id, "submission.accept", "content", content.id)
    else:
        content.status = "rejected"
        write_audit(session, user.id, "submission.reject", "content", content.id)
        drop_pushes(session, content.id)
    session.commit()
    return {"content_id": content.id, "status": content.status}


@router.post("/{channel_id}/pushes/{content_id}")
def push_room_post(
    channel_id: str,
    content_id: str,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    room = _owner_channel(session, channel_id, user)
    if room.kind != "room" or not room.parent_channel_id:
        raise APIError(400, "PARENT_REQUIRED", "只能把房间帖子推到所属频道")
    if room.is_private:
        raise APIError(403, "ROOM_PRIVATE", "私密房间内容不能推送到公开频道")
    content = session.get(Content, content_id)
    item = session.get(ChannelItem, (room.id, content_id))
    if content is None or item is None or content.status != "published":
        raise APIError(409, "CONTENT_NOT_PUBLISHED", "只有已公开的房间帖子可以推送")
    existing = session.get(RoomPostPush, content.id)
    if existing is None:
        now = utcnow()
        session.add(
            RoomPostPush(
                content_id=content.id,
                room_id=room.id,
                channel_id=room.parent_channel_id,
                pushed_by=user.id,
                pushed_at=now,
            )
        )
        session.add(
            ChannelItem(
                channel_id=room.parent_channel_id,
                content_id=content.id,
                origin_room_id=room.id,
                added_at=now,
            )
        )
        write_audit(session, user.id, "room.push", "content", content.id)
        session.commit()
    return {"content_id": content.id, "channel_id": room.parent_channel_id}


@router.delete("/{channel_id}/pushes/{content_id}")
def unpush_room_post(
    channel_id: str,
    content_id: str,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, bool]:
    room = _owner_channel(session, channel_id, user)
    push = session.get(RoomPostPush, content_id)
    if push is None or push.room_id != room.id:
        raise APIError(404, "CONTENT_NOT_FOUND", "这条帖子没有推到频道")
    drop_pushes(session, content_id)
    write_audit(session, user.id, "room.unpush", "content", content_id)
    session.commit()
    return {"pushed": False}
