import json

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, field_validator
from sqlalchemy import and_, delete, exists, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.api.v1.auth import current_user, optional_user, require_verified_phone
from app.api.v1.uploads import owned_upload
from app.core.pagination import decode_cursor, encode_cursor, paginate_rows
from app.feed import MAX_LISTING_IMAGES, image_keys_of, author_names, card_extras, content_titles, listing_map, reaction_flags, repost_context
from app.recommend import country_blocked, effective_region
from app.reports import ReportBody, limit_reports, report_receipt
from app.core.audit import write_audit
from app.core.db import get_db
from app.core.errors import APIError
from app.core.regions import open_regions
from app.embed import embed_fields
from app.guard import blocked_term_in, check_hourly_limit
from app.models import (
    Channel,
    ChannelCollaborator,
    ChannelItem,
    ChannelRoomSlot,
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
from app.privacy import is_room_member, viewable
from app.rooms import (
    ROOM_LIMIT,
    ROOM_TYPE_LABELS,
    SORT_BASIS,
    drop_pushes,
    episode_sort_key,
    film_sort_key,
    notify_room_update,
    require_not_banned,
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
        Channel.region_code.in_(list(open_regions(session))),  # 后台关闭的国家，频道不再列出
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
    region = effective_region(session, user)
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
    ][:5]
    return {"items": items}


@router.get("/mine")
def my_rooms(
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, list[dict[str, object]]]:
    """我管的房间（房主或协作者、没被拒），给发布页的「发布到」用；剧集 / 视频房间前端跳回房间里添加。新建的在前。"""
    collab = select(ChannelCollaborator.channel_id).where(ChannelCollaborator.user_id == user.id)
    rows = session.scalars(
        select(Channel)
        .where(
            Channel.kind == "room",
            Channel.visibility == "public",
            Channel.review_status != "rejected",
            or_(Channel.owner_id == user.id, Channel.id.in_(collab)),
        )
        .order_by(Channel.created_at.desc())
    ).all()
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


def _channel_rooms(session: Session, channel: Channel) -> list[dict[str, object]]:
    """频道里的房间位：只列后台指定的（推荐 / VIP），按排序号；房间自己的父频道不再决定它出现在哪。"""
    rows = session.execute(
        select(Channel, ChannelRoomSlot.label)
        .join(ChannelRoomSlot, ChannelRoomSlot.room_id == Channel.id)
        .where(
            ChannelRoomSlot.channel_id == channel.id,
            or_(ChannelRoomSlot.expires_at.is_(None), ChannelRoomSlot.expires_at > utcnow()),
            Channel.kind == "room",
            Channel.visibility == "public",
            Channel.is_active.is_(True),
            Channel.is_private.is_(False),
        )
        .order_by(ChannelRoomSlot.sort_order, Channel.name_hans)
    ).all()
    published_ids = set(
        session.scalars(
            select(ChannelItem.channel_id)
            .join(Content, Content.id == ChannelItem.content_id)
            .where(
                ChannelItem.channel_id.in_([row.id for row, _ in rows] or [""]),
                Content.status == "published",
                Content.deleted_at.is_(None),
            )
            .distinct()
        ).all()
    )
    return [
        {
            "id": row.id,
            "name_hans": row.name_hans,
            "room_type": row.room_type,
            "room_type_label": ROOM_TYPE_LABELS.get(row.room_type, row.room_type),
            "is_private": row.is_private,
            "is_active": row.is_active,
            "has_published": row.id in published_ids,
            "slot_label": label,
        }
        for row, label in rows
    ]


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
        "cover_key": channel.cover_key,
        "intro": channel.intro or "",
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
        "rooms": _channel_rooms(session, channel),
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
    query = (
        select(ChannelItem)
        .join(Content, Content.id == ChannelItem.content_id)
        .where(
            ChannelItem.channel_id == channel.id,
            visible,
            Content.deleted_at.is_(None),
            viewable(user.id if user else None),  # 在数据库里过滤，不再每条内容查一次库
            *([ChannelItem.season == season] if season is not None else []),
        )
        .options(joinedload(ChannelItem.content))
    )
    bounded = min(max(limit, 1), 50)
    parts = decode_cursor(cursor) if cursor else None
    if channel.room_type in {"series", "film", "video"}:
        # 剧集 / 片单 / 视频房间按集号、片单顺序排，条目本来就不多：整份读出来再按游标截取
        rows = session.scalars(
            query.order_by(ChannelItem.pinned.desc(), ChannelItem.sort_key.asc(), ChannelItem.added_at.asc())
        ).unique().all()
        page, next_cursor = paginate_rows(list(rows), cursor, bounded, "content_id", "added_at")
    else:
        # 按时间的频道（官方频道会一直变长）：在数据库里从游标那条往后取一页，不再把全部帖子读进内存
        anchor = session.get(ChannelItem, (channel.id, parts[0])) if parts and len(parts) == 2 else None
        if anchor is not None:
            later = and_(
                ChannelItem.pinned.is_(anchor.pinned),
                or_(
                    ChannelItem.added_at < anchor.added_at,
                    and_(ChannelItem.added_at == anchor.added_at, ChannelItem.content_id < anchor.content_id),
                ),
            )
            # 置顶的排在最前：游标停在置顶条目上时，后面还有全部非置顶的
            query = query.where(or_(ChannelItem.pinned.is_(False), later) if anchor.pinned else later)
        rows = session.scalars(
            query.order_by(ChannelItem.pinned.desc(), ChannelItem.added_at.desc(), ChannelItem.content_id.desc()).limit(bounded + 1)
        ).unique().all()
        page = list(rows[:bounded])
        next_cursor = encode_cursor(page[-1].content_id, page[-1].added_at.isoformat()) if len(rows) > bounded else None
    page_rows = page
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
    # 房主看自己房间时，每条帖子带上推送到频道的状态（待审 / 已推送 / 被拒），房间页据此显示按钮
    pushes: dict[str, tuple[str, str]] = {}
    if user is not None and channel.kind == "room" and channel.owner_id == user.id and page_rows:
        pushes = {
            push.content_id: (push.status, name)
            for push, name in session.execute(
                select(RoomPostPush, Channel.name_hans)
                .join(Channel, Channel.id == RoomPostPush.channel_id)
                .where(RoomPostPush.room_id == channel.id, RoomPostPush.content_id.in_([row.content_id for row in page_rows]))
            ).all()
        }
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
                "push_status": pushes.get(row.content_id, (None, None))[0],
                "push_channel_name": pushes.get(row.content_id, (None, None))[1],
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
    if next_cursor:
        payload["next_cursor"] = next_cursor
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
    parent_channel_id: str = ""  # 可不填：房间不属于任何频道；是否出现在某个频道里由后台的房间位决定
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
    # 和改名同一条规则：房间第一条帖子直接公开时房间会跟着上线，名字可能没人看过
    if blocked_term_in(session, body.name):
        raise APIError(422, "VALIDATION_FAILED", "房间名包含不允许的词，换一个吧")
    parent = _official_parent(session, body.parent_channel_id) if body.parent_channel_id else None
    owned = session.scalar(select(func.count()).select_from(Channel).where(Channel.owner_id == user.id))
    if not user.is_trusted and (owned or 0) >= ROOM_LIMIT:
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
        region_code=parent.region_code if parent is not None else effective_region(session, user),
        owner_id=user.id,
        parent_channel_id=parent.id if parent is not None else None,
        is_active=False,
        is_private=body.is_private,
        review_status="pending",
    )
    session.add(channel)
    write_audit(session, user.id, "channel.create", "channel", channel.id)
    session.commit()
    return {"channel_id": channel.id, "review_status": channel.review_status, "room_type": channel.room_type}


class RoomEditBody(BaseModel):
    """房主改房间：名字、类型都可选，只改传了的。"""

    room_type: str | None = None
    name: str | None = None
    cover_key: str | None = None  # 房间封面图；传空字符串表示去掉封面
    is_private: bool | None = None  # 私密 / 公开可以随时互相切换
    intro: str | None = None  # 房间介绍；空字符串表示清空

    @field_validator("intro")
    @classmethod
    def intro_length(cls, value: str | None) -> str | None:
        if value is None:
            return None
        intro = value.strip()
        if len(intro) > 250:  # 和个人介绍一样
            raise ValueError("房间介绍最多 250 个字")
        return intro

    @field_validator("room_type")
    @classmethod
    def known_room_type(cls, value: str | None) -> str | None:
        if value is not None and value not in _ROOM_TYPES:
            raise ValueError("房间类型不正确")
        return value

    @field_validator("name")
    @classmethod
    def name_length(cls, value: str | None) -> str | None:
        return None if value is None else RoomBody.name_length(value)


@router.patch("/{channel_id}")
def update_room(
    channel_id: str,
    body: RoomEditBody,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    channel = _owner_channel(session, channel_id, user)
    if channel.kind != "room":
        raise APIError(404, "CHANNEL_NOT_FOUND", "频道不存在")
    if body.name is not None and body.name != channel.name_hans:
        # 通过审核后改名不再过人审，至少挡住敏感词
        if blocked_term_in(session, body.name):
            raise APIError(422, "VALIDATION_FAILED", "房间名包含不允许的词，换一个吧")
        channel.name_hans = body.name
        channel.name_hant = body.name
        write_audit(session, user.id, "channel.rename", "channel", channel.id, body.name)
    if body.room_type is not None:
        channel.room_type = body.room_type
    if body.cover_key is not None:
        if body.cover_key:
            _owned_media(session, user, body.cover_key, "image/", "图片")
        channel.cover_key = body.cover_key or None
    if body.intro is not None:
        if blocked_term_in(session, body.intro):
            raise APIError(422, "VALIDATION_FAILED", "房间介绍包含不允许的词，改一下吧")
        channel.intro = body.intro or None
    if body.is_private is not None and body.is_private != channel.is_private:
        channel.is_private = body.is_private
        if body.is_private:
            # 改成私密：已经推到频道里的帖子撤回，不然私密内容还挂在公开频道里
            pushed = session.scalars(select(RoomPostPush.content_id).where(RoomPostPush.room_id == channel.id)).all()
            for content_id in pushed:
                drop_pushes(session, content_id)
        else:
            # 改成公开：任何人都能直接加入，待审的加入申请没用了
            session.execute(delete(RoomJoinRequest).where(RoomJoinRequest.room_id == channel.id))
        write_audit(session, user.id, "channel.private" if body.is_private else "channel.public", "channel", channel.id)
    session.commit()
    return {
        "channel_id": channel.id,
        "room_type": channel.room_type,
        "name_hans": channel.name_hans,
        "is_private": channel.is_private,
    }


@router.delete("/{channel_id}")
def delete_room(
    channel_id: str,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    """房主删除自己的房间，不能恢复：只属于这个房间的帖子下架，留言删掉，成员关系清掉。"""
    from app.api.v1.admin import _delete_files  # 放在函数里：admin 模块会反过来引用本模块
    from app.api.v1.admin_channels import _purge_channel

    channel = _owner_channel(session, channel_id, user)
    if channel.kind != "room":
        raise APIError(404, "CHANNEL_NOT_FOUND", "频道不存在")
    name = channel.name_hans
    removed_posts, orphaned = _purge_channel(session, channel)
    # 房间删了以后日志里只剩 id，所以把名称和下架的数量写进备注
    write_audit(session, user.id, "channel.delete", "channel", channel_id, f"{name}，连同 {removed_posts} 条内容"[:300])
    session.commit()
    _delete_files(orphaned)
    return {"deleted": True, "removed_posts": removed_posts}


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


ENTRY_HOURLY_LIMIT = 30  # 房主一次加好几集，比普通发帖的每小时 5 条宽；仍然防刷


class MediaBody(TextBody):
    """标题 + 可选正文 + 图片 / 视频 / 视频外链：房主加条目、普通用户投稿共用。"""

    body: str = ""  # 可以不写：带图片或视频时正文可空
    image_keys: list[str] = []  # 最多 6 张，第一张作封面（电影卡片左侧）
    video_key: str | None = None
    video_url: str | None = None  # 视频外链（YouTube / 哔哩哔哩），和上传视频二选一

    @field_validator("body")
    @classmethod
    def body_length(cls, value: str) -> str:  # 覆盖 TextBody：允许空正文
        text = value.strip()
        if len(text) > 4000:
            raise ValueError("正文不能超过 4000 个字")
        return text

    @field_validator("image_keys")
    @classmethod
    def bounded_images(cls, value: list[str]) -> list[str]:
        keys = [key for key in dict.fromkeys(value) if key]
        if len(keys) > MAX_LISTING_IMAGES:
            raise ValueError(f"最多上传 {MAX_LISTING_IMAGES} 张图片")
        return keys


class EntryBody(MediaBody):
    season: int | None = None  # 页面不再让填季，不传就是第 1 季；旧数据里多季的房间照常显示
    episode: int | None = None
    rights_confirmed: bool = False


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


def _editor_ids(session: Session, channel: Channel) -> list[str]:
    """房主 + 协作者的 user id。"""
    ids = list(session.scalars(select(ChannelCollaborator.user_id).where(ChannelCollaborator.channel_id == channel.id)).all())
    return ids + [channel.owner_id] if channel.owner_id else ids


def _catalog_room(session: Session, channel_id: str, user: User) -> Channel:
    channel = _editor_channel(session, channel_id, user)
    # 审核中的房间也能先加条目（以待审身份进去，见 add_entry）；被拒或下线的不行
    if not channel.is_active and channel.review_status != "pending":
        raise APIError(403, "CHANNEL_PENDING", "房间没有通过审核，不能编排条目")
    if channel.room_type not in {"series", "film", "video"}:
        raise APIError(409, "ROOM_TYPE", "这个房间不能编排条目")
    return channel


def _catalog_rows(session: Session, channel_id: str, season: int | None = None) -> list[ChannelItem]:
    query = select(ChannelItem).where(ChannelItem.channel_id == channel_id, ChannelItem.sort_key != "")
    if season is not None:
        query = query.where(ChannelItem.season == season)
    return list(session.scalars(query.order_by(ChannelItem.sort_key)).all())


def _owned_media(session: Session, user: User, key: str, prefix: str, label: str) -> None:
    """只能用自己上传完成的文件，且类型要对（图片位不能塞视频，反之亦然）。"""
    if not owned_upload(session, user, key).content_type.startswith(prefix):
        raise APIError(400, "VALIDATION_FAILED", f"这里需要上传{label}")


def _media(session: Session, user: User, body: MediaBody) -> dict[str, object]:
    """图片 / 上传视频 / 视频外链 → Content 字段（带外链时调用方把 type 设为 embed）。只校验，不写库。"""
    video_url = (body.video_url or "").strip()
    if video_url and body.video_key:
        raise APIError(400, "VALIDATION_FAILED", "上传视频和视频外链只能选一个")
    embed = embed_fields(video_url) if video_url else {}  # 不在白名单 / 短链直接报错
    for key in body.image_keys:
        _owned_media(session, user, key, "image/", "图片")
    if body.video_key:
        _owned_media(session, user, body.video_key, "video/", "视频")
    return {
        "image_key": body.image_keys[0] if body.image_keys else None,
        "image_keys_json": json.dumps(body.image_keys),
        "video_key": body.video_key,
        **embed,
    }


@router.post("/{channel_id}/entries")
def add_entry(
    channel_id: str,
    body: EntryBody,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    channel = _catalog_room(session, channel_id, user)
    check_hourly_limit(session, user.id, ENTRY_HOURLY_LIMIT)
    media = _media(session, user, body)
    embed = "embed_provider_code" in media
    season = body.season if body.season is not None else 1
    episode = body.episode
    if channel.room_type == "series":
        if episode is None or not 1 <= season <= 99 or not 1 <= episode <= 999:
            raise APIError(400, "VALIDATION_FAILED", "剧集需要填集号（1 到 999）")
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
        season = None
        episode = None
        confirmed = not embed
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
        sort_key = film_sort_key(int(count or 0) + 1)
        confirmed = False
    now = utcnow()
    # 房间还在审核：条目先待审，管理员通过任一条后房间自动上线（同公告）。直接发布会经搜索、主页漏出去。
    # 命中敏感词也先待审：房主发的内容和普通发帖同一条规则
    waiting = not channel.is_active or blocked_term_in(session, body.title, body.body) is not None
    content = Content(
        type="post",
        status="pending" if waiting else "published",
        author_id=user.id,
        title=body.title,
        summary=body.body[:500],
        body=body.body,
        source_name=user.display_name,
        published_at=None if waiting else now,
        **media,
    )
    if embed:
        content.type = "embed"
    session.add(content)
    session.flush()
    session.add(
        ChannelItem(
            channel_id=channel.id,
            content_id=content.id,
            sort_key=sort_key,
            season=season,
            episode=episode,
            rights_confirmed=confirmed,
            added_at=now,
        )
    )
    if not waiting:
        notify_room_update(session, channel, content)
    session.commit()
    return {"content_id": content.id, "sort_key": sort_key, "status": content.status}


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
    request: Request,
    user: User | None = Depends(optional_user),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    limit_reports(session, request, user)
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
    check_hourly_limit(session, user.id)
    now = utcnow()
    # 房间在审核中，或公告命中敏感词：先待审，管理员通过后才公开、才通知成员
    waiting = not channel.is_active or blocked_term_in(session, body.title, body.body) is not None
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
    session.add(ChannelItem(channel_id=channel.id, content_id=content.id, pinned=channel.is_active, added_at=now))
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
            Content.published_at.is_(None),  # 公开过又被举报隐藏的归后台复核，房主不能自己放回去
            Content.deleted_at.is_(None),
            Content.author_id.not_in(_editor_ids(session, channel)),
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
                "image_keys": image_keys_of(content),  # 房主审核时要看到图片 / 视频
                "video_key": content.video_key,
                "embed_source_url": content.embed_source_url,
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
    body: MediaBody,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    require_verified_phone(user, "投稿")
    channel = session.get(Channel, channel_id)
    if channel is None or not channel.is_active or channel.visibility != "public":
        raise APIError(404, "CHANNEL_NOT_FOUND", "频道不存在")
    if channel.kind == "room" and channel.is_private and not is_room_member(session, channel, user):
        raise APIError(403, "ROOM_PRIVATE", "加入私密房间后才能投稿")
    require_not_banned(session, [channel.id], user.id)
    if country_blocked(session, user, channel):
        raise APIError(403, "REGION_BLOCKED", "当前国家看不到这个频道")
    check_hourly_limit(session, user.id)
    if not (body.body or body.image_keys or body.video_key or (body.video_url or "").strip()):
        raise APIError(400, "VALIDATION_FAILED", "正文、图片、视频至少要有一样")
    media = _media(session, user, body)
    now = utcnow()
    content = Content(
        type="embed" if "embed_provider_code" in media else "post",
        status="pending",
        author_id=user.id,
        title=body.title,
        summary=body.body[:500],
        body=body.body,
        source_name=user.display_name,
        **media,
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
    if content.status != "pending" or content.published_at is not None:
        raise APIError(409, "CONTENT_ALREADY_DECIDED", "这条投稿已经处理过")
    if content.author_id in _editor_ids(session, channel):
        # 房主 / 协作者自己发的帖子在等平台审核，不能在房间里自己放行
        raise APIError(403, "FORBIDDEN", "自己发的内容由平台审核，不能在房间里通过")
    now = utcnow()
    if body.decision == "accept":
        # 房主放行也不能绕过平台的敏感词 / 链接黑名单
        if blocked_term_in(session, content.title, content.body):
            raise APIError(422, "BLOCKED_TERM", "这条投稿包含不允许的词或链接，只能拒绝")
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


class PushBody(BaseModel):
    channel_id: str = ""  # 推到哪个官方频道；不填则用房间的父频道（旧客户端）


MAX_PENDING_PUSHES = 10  # 一个房间同时等审核的推送上限，免得审核队列被刷满


@router.post("/{channel_id}/pushes/{content_id}")
def push_room_post(
    channel_id: str,
    content_id: str,
    body: PushBody | None = None,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    """房主把房间里的帖子推到任意官方频道。推送先等后台审核，通过后才在频道里出现（审核见 admin_channels）。"""
    room = _owner_channel(session, channel_id, user)
    if room.kind != "room":
        raise APIError(400, "NOT_A_ROOM", "只有房间的帖子可以推送")
    if room.is_private:
        raise APIError(403, "ROOM_PRIVATE", "私密房间内容不能推送到公开频道")
    target_id = (body.channel_id if body else "") or room.parent_channel_id
    if not target_id:
        raise APIError(400, "CHANNEL_REQUIRED", "请选择要推送到的频道")
    target = session.get(Channel, target_id)
    if target is None or not target.is_active or target.visibility != "public" or not target.kind.startswith("official"):
        raise APIError(404, "CHANNEL_NOT_FOUND", "频道不存在")
    content = session.get(Content, content_id)
    item = session.get(ChannelItem, (room.id, content_id))
    if content is None or item is None or content.status != "published":
        raise APIError(409, "CONTENT_NOT_PUBLISHED", "只有已公开的房间帖子可以推送")
    existing = session.get(RoomPostPush, content.id)
    if existing is not None and existing.status == "rejected":
        session.delete(existing)  # 被拒的可以改推别的频道或再推一次
        session.flush()
        existing = None
    if existing is None:
        pending = session.scalar(
            select(func.count()).select_from(RoomPostPush).where(RoomPostPush.room_id == room.id, RoomPostPush.status == "pending")
        )
        if (pending or 0) >= MAX_PENDING_PUSHES:
            raise APIError(409, "PUSH_PENDING_LIMIT", f"最多同时有 {MAX_PENDING_PUSHES} 条推送在等审核")
        session.add(
            RoomPostPush(content_id=content.id, room_id=room.id, channel_id=target.id, pushed_by=user.id, pushed_at=utcnow(), status="pending")
        )
        write_audit(session, user.id, "room.push", "content", content.id)
        session.commit()
        return {"content_id": content.id, "channel_id": target.id, "status": "pending"}
    return {"content_id": content.id, "channel_id": existing.channel_id, "status": existing.status}


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
