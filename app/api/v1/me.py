import re
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.orm import Session

from app.api.v1.auth import current_user, optional_user
from app.api.v1.uploads import delete_object, owned_upload
from app.core.audit import write_audit
from app.core.db import get_db
from app.core.errors import APIError
from app.core.pagination import decode_cursor, encode_cursor
from app.core.regions import open_regions
from app.feed import build_following_feed, paginate_feed
from app.guard import blocked_term_in
from app.keywords import clean_city_topic
from app.privacy import can_view_content
from app.recommend import country_blocked, for_you, is_roaming
from app.reports import REASONS, SLA
from app.rooms import ROOM_LIMIT, ROOM_TYPE_LABELS
from app.models import (
    Channel,
    ChannelItem,
    ChannelSubscription,
    ConsentRecord,
    Content,
    ContentReaction,
    DmMessage,
    DmThread,
    ListingExt,
    ModerationCase,
    Notification,
    RefreshSession,
    RoomBan,
    RoomComment,
    UploadObject,
    User,
    UserBlock,
    UserFollow,
    RegionOpenRequest,
    UserRegionPref,
    as_utc,
    utcnow,
)

router = APIRouter(prefix="/me")


@router.get("")
def my_profile(user: User = Depends(current_user), session: Session = Depends(get_db)) -> dict[str, object]:
    consent = session.scalar(
        select(ConsentRecord.version).where(ConsentRecord.user_id == user.id).order_by(ConsentRecord.created_at.desc()).limit(1)
    )
    return {
        "user_id": user.id,
        "email": user.email,
        "consent_version": consent,
        "display_name": user.display_name,
        "handle": user.handle or "",
        "avatar_tone": user.avatar_tone,
        "avatar_key": user.avatar_key or "",
        "city_label": user.city_label or "",
        "bio": user.bio or "",
        "script_pref": user.script_pref,
        "phone": user.phone or "",
        "is_admin": user.is_admin,  # 前端据此决定是否显示管理后台入口；权限仍由后端校验
        "is_super": user.is_super,
    }


class ProfilePatch(BaseModel):
    display_name: str | None = None
    handle: str | None = None
    avatar_tone: str | None = None
    avatar_key: str | None = None  # 已上传图片的 key；空字符串表示去掉头像
    city_label: str | None = None
    bio: str | None = None  # 个人介绍；空字符串表示清空

    @field_validator("bio")
    @classmethod
    def bio_length(cls, value: str | None) -> str | None:
        if value is None:
            return None
        bio = value.strip()
        if len(bio) > 250:  # 和抖音简介一样
            raise ValueError("个人介绍最多 250 个字")
        return bio

    @field_validator("display_name")
    @classmethod
    def display_name_length(cls, value: str | None) -> str | None:
        if value is None:
            return None
        name = value.strip()
        if not name or len(name) > 40:
            raise ValueError("显示名需要 1 到 40 个字")
        return name

    @field_validator("handle")
    @classmethod
    def handle_shape(cls, value: str | None) -> str | None:
        if value is None:
            return None
        handle = value.strip().lstrip("@").lower()
        if not re.fullmatch(r"[a-z0-9._]{1,20}", handle):
            raise ValueError("账号名需要 1 到 20 位字母、数字、点或下划线")
        return handle

    @field_validator("avatar_tone")
    @classmethod
    def tone_letter(cls, value: str | None) -> str | None:
        if value is None:
            return None
        tone = value.strip().lower()
        if tone not in {"a", "b", "c", "d", "e", "f"}:
            raise ValueError("头像色不正确")
        return tone

    @field_validator("city_label")
    @classmethod
    def city_label_token(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value.strip():
            return ""
        return clean_city_topic(value)


class SubscriptionPatch(BaseModel):
    is_muted: bool


def drop_avatar(session: Session, user: User) -> None:
    """去掉头像并删掉图片文件（换头像、本人移除、后台移除都走这里）。不提交。"""
    if not user.avatar_key:
        return
    delete_object(user.avatar_key)
    session.execute(delete(UploadObject).where(UploadObject.key == user.avatar_key))
    user.avatar_key = None


@router.patch("")
def update_profile(
    body: ProfilePatch,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    if body.display_name is not None:
        user.display_name = body.display_name
    if body.handle is not None and body.handle != user.handle:
        taken = session.scalar(select(User.id).where(User.handle == body.handle, User.id != user.id))
        if taken is not None:
            raise APIError(409, "DUPLICATE_HANDLE", "这个账号名已经有人用了")
        user.handle = body.handle
    if body.avatar_tone is not None:
        user.avatar_tone = body.avatar_tone
    if body.avatar_key is not None and body.avatar_key != (user.avatar_key or ""):
        if body.avatar_key and not owned_upload(session, user, body.avatar_key).content_type.startswith("image/"):
            raise APIError(400, "AVATAR_NOT_IMAGE", "头像只能用图片")
        drop_avatar(session, user)
        user.avatar_key = body.avatar_key or None
    if body.city_label is not None:
        user.city_label = body.city_label or None
    if body.bio is not None:
        if blocked_term_in(session, body.bio):
            raise APIError(422, "VALIDATION_FAILED", "个人介绍包含不允许的词，改一下吧")
        user.bio = body.bio or None
    session.commit()
    return my_profile(user, session)


def _content_paused(session: Session, user: User, content_id: str) -> bool:
    placements = session.scalars(select(ChannelItem).where(ChannelItem.content_id == content_id)).all()
    channels = [channel for row in placements if (channel := session.get(Channel, row.channel_id)) is not None]
    if not channels:
        return False
    return all(country_blocked(session, user, channel) for channel in channels)


def _mark_seen_divider(items: list[dict[str, object]], seen_at: datetime | None) -> int:
    fresh_count = 0
    placed = False
    for item in items:
        added = as_utc(datetime.fromisoformat(str(item["added_at"])))
        fresh = not item.get("pinned") and seen_at is not None and added > as_utc(seen_at)
        if fresh:
            fresh_count += 1
        item["show_divider_before"] = False
        if placed or item.get("pinned") or fresh:
            continue
        item["show_divider_before"] = True
        placed = True
    return fresh_count


def active_channel(session: Session, channel_id: str) -> Channel:
    channel = session.get(Channel, channel_id)
    if channel is None or not channel.is_active or channel.visibility != "public":
        raise APIError(404, "CHANNEL_NOT_FOUND", "频道不存在")
    return channel


@router.put("/subscriptions/{channel_id}")
def join_channel(
    channel_id: str,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    channel = active_channel(session, channel_id)
    if channel.kind == "room" and channel.is_private and channel.owner_id != user.id:
        raise APIError(403, "ROOM_JOIN_APPROVAL_REQUIRED", "私密房间需要先申请并由房主批准")
    if country_blocked(session, user, channel):
        raise APIError(403, "REGION_BLOCKED", "当前国家看不到这个频道")
    if session.get(RoomBan, (channel.id, user.id)) is not None:
        raise APIError(403, "ROOM_BANNED", "房主已把你移出这个房间，不能再加入")
    subscription = session.get(ChannelSubscription, (user.id, channel.id))
    if subscription is None:
        session.add(ChannelSubscription(user_id=user.id, channel_id=channel.id))
        channel.bump_subscribers(1)
        session.commit()
    return {"joined": True, "subscriber_count": channel.subscriber_count}


def _unread_counts(session: Session, user_id: str) -> dict[str, int]:
    """这个人每个已加入频道的未读条数，一条查询算完（不按频道一个个查）。"""
    rows = session.execute(
        select(ChannelItem.channel_id, func.count())
        .join(Content, Content.id == ChannelItem.content_id)
        .join(
            ChannelSubscription,
            and_(ChannelSubscription.channel_id == ChannelItem.channel_id, ChannelSubscription.user_id == user_id),
        )
        .where(
            Content.status == "published",
            Content.deleted_at.is_(None),
            ChannelItem.added_at > ChannelSubscription.last_read_at,
        )
        .group_by(ChannelItem.channel_id)
    ).all()
    return {channel_id: int(count) for channel_id, count in rows}


@router.get("/subscriptions")
def list_subscriptions(
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    rows = session.scalars(select(ChannelSubscription).where(ChannelSubscription.user_id == user.id)).all()
    items: list[dict[str, object]] = []
    paused = 0
    unread = _unread_counts(session, user.id)
    for subscription in rows:
        channel = session.get(Channel, subscription.channel_id)
        if channel is None:
            continue
        count = unread.get(channel.id, 0)
        subscription.unread_count = count
        if country_blocked(session, user, channel):
            paused += 1
            continue
        items.append(
            {
                "channel_id": channel.id,
                "code": channel.code,
                "name_hans": channel.name_hans,
                "is_muted": subscription.is_muted,
                "unread_count": count,
            }
        )
    session.commit()
    return {"items": items, "paused_count": paused}


@router.delete("/subscriptions/{channel_id}")
def leave_channel(
    channel_id: str,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, bool]:
    subscription = session.get(ChannelSubscription, (user.id, channel_id))
    if subscription is None:
        raise APIError(404, "SUBSCRIPTION_NOT_FOUND", "还没有加入这个频道")
    channel = session.get(Channel, channel_id)
    if channel is not None:
        channel.bump_subscribers(-1)
    session.delete(subscription)
    write_audit(session, user.id, "subscription.leave", "channel", channel_id)
    session.commit()
    return {"joined": False}


@router.patch("/subscriptions/{channel_id}")
def update_subscription(
    channel_id: str,
    body: SubscriptionPatch,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    active_channel(session, channel_id)
    subscription = session.get(ChannelSubscription, (user.id, channel_id))
    if subscription is None:
        raise APIError(404, "SUBSCRIPTION_NOT_FOUND", "还没有加入这个频道")
    subscription.is_muted = body.is_muted
    session.commit()
    return {"is_muted": subscription.is_muted}


@router.get("/channels")
def my_channels(
    cursor: str | None = None,
    limit: int = 20,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    rows = session.scalars(select(Channel).where(Channel.owner_id == user.id).order_by(Channel.created_at.desc())).all()
    owned_ids = {row.id for row in rows}
    joined = session.scalars(
        select(Channel)
        .join(ChannelSubscription, ChannelSubscription.channel_id == Channel.id)
        .where(ChannelSubscription.user_id == user.id, Channel.kind == "room")
        .order_by(ChannelSubscription.joined_at.desc())
    ).all()
    listed = [(row, "owner") for row in rows]
    listed.extend((row, "member") for row in joined if row.id not in owned_ids)
    items: list[dict[str, object]] = []
    paused = 0
    for row, role in listed:
        if country_blocked(session, user, row):
            paused += 1
            continue
        parent = session.get(Channel, row.parent_channel_id) if row.parent_channel_id else None
        entry_count = session.scalar(
            select(func.count())
            .select_from(ChannelItem)
            .join(Content, Content.id == ChannelItem.content_id)
            .where(
                ChannelItem.channel_id == row.id,
                Content.status == "published",
                Content.deleted_at.is_(None),
            )
        )
        items.append(
            {
                "channel_id": row.id,
                "name_hans": row.name_hans,
                "room_type": row.room_type,
                "room_type_label": ROOM_TYPE_LABELS.get(row.room_type, row.room_type),
                "is_private": row.is_private,
                "is_active": row.is_active,
                "review_status": row.review_status,
                "parent_channel_id": row.parent_channel_id,
                "parent_name_hans": parent.name_hans if parent is not None else "",
                "entry_count": int(entry_count or 0),
                "role": role,
            }
        )
    start = 0
    if cursor:
        parts = decode_cursor(cursor)
        if parts and parts[0]:
            for index, item in enumerate(items):
                if item["channel_id"] == parts[0]:
                    start = index + 1
                    break
    bounded = min(max(limit, 1), 50)
    page = items[start : start + bounded]
    next_cursor = None
    if start + bounded < len(items) and page:
        next_cursor = encode_cursor(str(page[-1]["channel_id"]))
    payload: dict[str, object] = {
        "items": page,
        "paused_count": paused,
        "owned_count": len(rows),
        "room_limit": ROOM_LIMIT,
        "quota_used": len(rows),
    }
    if next_cursor:
        payload["next_cursor"] = next_cursor
    return payload


@router.get("/badges")
def badges(user: User = Depends(current_user), session: Session = Depends(get_db)) -> dict[str, int]:
    notes = session.scalar(
        select(func.count()).select_from(Notification).where(Notification.user_id == user.id, Notification.read_at.is_(None))
    )
    # 别人发给我、我还没读的私信，一条查询算完。会话只有两个人，所以发信人就是对方；双方任一拉黑了对方就不算。
    blocked = (
        select(UserBlock.user_id)
        .where(
            or_(
                and_(UserBlock.user_id == user.id, UserBlock.target_id == DmMessage.sender_id),
                and_(UserBlock.user_id == DmMessage.sender_id, UserBlock.target_id == user.id),
            )
        )
        .exists()
    )
    messages = int(
        session.scalar(
            select(func.count())
            .select_from(DmMessage)
            .join(DmThread, DmThread.id == DmMessage.thread_id)
            .where(
                or_(DmThread.user_low == user.id, DmThread.user_high == user.id),
                DmMessage.sender_id != user.id,
                DmMessage.read_at.is_(None),
                ~blocked,
            )
        )
        or 0
    )
    notification_count = int(notes or 0)
    return {"notifications": notification_count, "messages": messages, "total": notification_count + messages}


@router.get("/notifications")
def my_notifications(
    cursor: str | None = None,
    limit: int = 20,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    # 通知只增不减：在数据库里按 (时间, id) 从游标往后取一页，未读数也在数据库里数，不再把全部通知读进内存
    unread = session.scalar(
        select(func.count()).select_from(Notification).where(Notification.user_id == user.id, Notification.read_at.is_(None))
    ) or 0
    bounded = min(max(limit, 1), 50)
    query = select(Notification).where(Notification.user_id == user.id)
    parts = decode_cursor(cursor) if cursor else None
    anchor = session.get(Notification, parts[0]) if parts and len(parts) == 2 else None
    if anchor is not None and anchor.user_id == user.id:
        query = query.where(
            or_(
                Notification.created_at < anchor.created_at,
                and_(Notification.created_at == anchor.created_at, Notification.id < anchor.id),
            )
        )
    rows = session.scalars(query.order_by(Notification.created_at.desc(), Notification.id.desc()).limit(bounded + 1)).all()
    page = rows[:bounded]
    next_cursor = encode_cursor(page[-1].id, page[-1].created_at.isoformat()) if len(rows) > bounded else None
    payload: dict[str, object] = {
        "items": [
            {
                "id": row.id,
                "kind": row.kind,
                "body": row.body,
                "content_id": row.content_id,
                "unread": row.read_at is None,
                "created_at": row.created_at.isoformat(),
            }
            for row in page
        ],
        "unread_count": unread,
    }
    if next_cursor:
        payload["next_cursor"] = next_cursor
    return payload


@router.get("/reports")
def my_reports(user: User = Depends(current_user), session: Session = Depends(get_db)) -> dict[str, list[dict[str, object]]]:
    rows = session.scalars(
        select(ModerationCase)
        .where(ModerationCase.reporter_id == user.id)
        .order_by(ModerationCase.created_at.desc())
    ).all()
    return {
        "items": [
            {
                "case_id": row.id,
                "reason": row.reason,
                "reason_text": REASONS.get(row.reason, row.reason),
                "detail": row.detail,
                "status": row.status,
                "sla": SLA,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]
    }


@router.post("/notifications/read-all")
def read_all_notifications(user: User = Depends(current_user), session: Session = Depends(get_db)) -> dict[str, int]:
    rows = session.scalars(
        select(Notification).where(Notification.user_id == user.id, Notification.read_at.is_(None))
    ).all()
    now = utcnow()
    for row in rows:
        row.read_at = now
    session.commit()
    return {"marked": len(rows)}


@router.patch("/notifications/{notification_id}/read")
@router.post("/notifications/{notification_id}/read")
def read_notification(
    notification_id: str,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, bool]:
    row = session.get(Notification, notification_id)
    if row is None or row.user_id != user.id:
        raise APIError(404, "NOTIFICATION_NOT_FOUND", "通知不存在")
    if row.read_at is None:
        row.read_at = utcnow()
        session.commit()
    return {"unread": False}


@router.get("/posts")
def my_posts(user: User = Depends(current_user), session: Session = Depends(get_db)) -> dict[str, list[dict[str, object]]]:
    rows = session.scalars(
        select(Content)
        .where(Content.author_id == user.id, Content.deleted_at.is_(None))
        .order_by(Content.created_at.desc())
    ).all()
    # 分类信息带上「是否已结案」：「我的发布」里据此显示「续期」/「已成交」
    closed = set(
        session.scalars(
            select(ListingExt.content_id).where(
                ListingExt.content_id.in_([row.id for row in rows if row.type == "listing"] or [""]),
                ListingExt.closed_reason.is_not(None),
            )
        )
    )
    return {
        "items": [
            {
                "content_id": row.id,
                "title": row.title,
                "status": row.status,
                "summary": row.summary,
                "type": row.type,
                "closed": row.id in closed,
            }
            for row in rows
        ]
    }


@router.get("/favorites")
def my_favorites(user: User = Depends(current_user), session: Session = Depends(get_db)) -> dict[str, object]:
    rows = session.scalars(
        select(Content)
        .join(ContentReaction, ContentReaction.content_id == Content.id)
        .where(
            ContentReaction.user_id == user.id,
            ContentReaction.favorited.is_(True),
            Content.deleted_at.is_(None),
            Content.status == "published",
        )
        .order_by(Content.published_at.desc())
    ).all()
    saved: list[dict[str, object]] = []
    paused_saved = 0
    for row in rows:
        if _content_paused(session, user, row.id) or not can_view_content(session, row, user):
            paused_saved += 1
            continue
        saved.append({"content_id": row.id, "title": row.title, "type": row.type, "summary": row.summary})
    follows = session.scalars(select(ChannelSubscription).where(ChannelSubscription.user_id == user.id)).all()
    visible_follows = 0
    paused_follows = 0
    for subscription in follows:
        channel = session.get(Channel, subscription.channel_id)
        if channel is not None and country_blocked(session, user, channel):
            paused_follows += 1
        else:
            visible_follows += 1
    return {
        "saved_count": len(saved),
        "followed_count": visible_follows,
        "paused_count": paused_saved + paused_follows,
        "items": saved,
    }


@router.get("/feed")
def my_feed(
    cursor: str | None = None,
    limit: int = 20,
    tab: str = "following",
    order: str = "ranked",
    viewer: User | None = Depends(optional_user),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    # 「为你推荐」游客也能看（不个性化，按新鲜度 / 活跃度 / 官方精选排序）；关注流必须登录。
    if tab == "foryou":
        user = viewer
        if order not in {"ranked", "time"}:
            raise APIError(400, "VALIDATION_FAILED", "排序只能是推荐或时间")
        bounded_foryou = min(max(limit, 1), 50)
        ranked_items = for_you(session, user, None, order)
        items, next_cursor = paginate_feed(ranked_items, cursor, bounded_foryou)
        payload: dict[str, object] = {"items": items, "seen_at": None}
        if next_cursor:
            payload["next_cursor"] = next_cursor
        return payload
    if viewer is None:
        raise APIError(401, "UNAUTHENTICATED", "请先登录")
    user = viewer
    bounded = min(max(limit, 1), 50)
    all_items = build_following_feed(session, user.id)
    subscriptions = session.scalars(
        select(ChannelSubscription).where(ChannelSubscription.user_id == user.id)
    ).all()
    paused_ids: set[str] = set()
    joined_count = 0
    for subscription in subscriptions:
        channel = session.get(Channel, subscription.channel_id)
        if channel is not None and country_blocked(session, user, channel):
            paused_ids.add(channel.id)
            continue
        joined_count += 1
    visible = [item for item in all_items if item.get("channel_id") not in paused_ids]
    fresh_count = _mark_seen_divider(visible, user.feed_seen_at)
    items, next_cursor = paginate_feed(visible, cursor, bounded)
    payload: dict[str, object] = {
        "items": items,
        "joined_count": joined_count,
        "paused_count": len(paused_ids),
        "new_count": sum(1 for item in visible if item.get("is_unread")),
        "fresh_count": fresh_count,
        "seen_at": user.feed_seen_at.isoformat() if user.feed_seen_at else None,
    }
    if next_cursor:
        payload["next_cursor"] = next_cursor
    return payload


@router.post("/feed/seen")
def mark_feed_seen(user: User = Depends(current_user), session: Session = Depends(get_db)) -> dict[str, str]:
    user.feed_seen_at = utcnow()
    # 关注流里的「未读」按每个频道的 last_read_at 算：看过关注流就把它们一起推到现在，
    # 不然加入频道之后的每条帖子永远标着未读（前端从不单独调「标记频道已读」）。
    session.execute(update(ChannelSubscription).where(ChannelSubscription.user_id == user.id).values(last_read_at=user.feed_seen_at))
    session.commit()
    return {"seen_at": user.feed_seen_at.isoformat()}


class RegionBody(BaseModel):
    region_code: str
    # 上限和数据库列宽一致：超了在 PostgreSQL 上会直接 500
    source: str = Field(default="manual", max_length=32)
    consent_id: str | None = Field(default=None, max_length=36)
    locked: bool = False
    browse_region_code: str | None = None

    @field_validator("region_code")
    @classmethod
    def known_region(cls, value: str) -> str:
        code = value.strip().upper()
        if code == "":
            return "GLOBAL"
        if len(code) < 2 or len(code) > 8 or not code.isalpha():
            raise ValueError("国家代码不正确")
        return code

    @field_validator("browse_region_code")
    @classmethod
    def browse_open_region(cls, value: str | None) -> str | None:
        if value is None:
            return None
        code = value.strip().upper()
        return code  # 是否已开通要查库，在 set_region 里校验


def _station(session: Session, user: User) -> tuple[str, str]:
    if not is_roaming(session, user):
        return "", ""
    pref = session.get(UserRegionPref, user.id)
    code = pref.browse_region_code if pref is not None and pref.browse_region_code else ""
    return open_regions(session).get(code, ("", ""))


@router.get("/regions")
def get_region(user: User = Depends(current_user), session: Session = Depends(get_db)) -> dict[str, object]:
    row = session.get(UserRegionPref, user.id)
    station_name, station_city = _station(session, user)
    open_list = [{"code": code, "name": name, "city": city} for code, (name, city) in open_regions(session).items()]
    if row is None:
        return {
            "region_code": "GLOBAL",
            "source": "default",
            "locked": False,
            "roaming": False,
            "station_name": station_name,
            "station_city": station_city,
            "open_regions": open_list,
        }
    return {
        "region_code": row.region_code,
        "source": row.source,
        "locked": row.locked,
        "consent_id": row.consent_id,
        "browse_region_code": row.browse_region_code,
        "roaming": is_roaming(session, user),
        "station_name": station_name,
        "station_city": station_city,
        "updated_at": row.updated_at.isoformat(),
        "open_regions": open_list,
    }


class OpenRequestBody(BaseModel):
    region_code: str

    @field_validator("region_code")
    @classmethod
    def request_code(cls, value: str) -> str:
        code = value.strip().upper()
        if len(code) < 2 or len(code) > 8 or not code.isalpha():
            raise ValueError("国家代码不正确")
        if code in {"UK", "GLOBAL"}:
            raise ValueError("这个国家已经开通")
        return code


@router.get("/regions/requests")
def list_open_requests(user: User = Depends(current_user), session: Session = Depends(get_db)) -> dict[str, list[str]]:
    rows = session.scalars(
        select(RegionOpenRequest.region_code)
        .where(RegionOpenRequest.user_id == user.id)
        .order_by(RegionOpenRequest.region_code)
    ).all()
    return {"region_codes": list(rows)}


@router.post("/regions/requests")
def request_open_region(
    body: OpenRequestBody,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    existing = session.scalar(
        select(RegionOpenRequest).where(
            RegionOpenRequest.user_id == user.id,
            RegionOpenRequest.region_code == body.region_code,
        )
    )
    if existing is None:
        session.add(RegionOpenRequest(user_id=user.id, region_code=body.region_code))
        session.commit()
    return {"region_code": body.region_code, "status": "recorded"}


@router.post("/regions")
def set_region(
    body: RegionBody,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    if body.browse_region_code and body.browse_region_code not in open_regions(session):
        raise APIError(422, "VALIDATION_FAILED", "只能浏览已开通的国家")
    row = session.get(UserRegionPref, user.id)
    now = utcnow()
    if row is not None and row.locked and body.region_code != row.region_code:
        raise APIError(409, "REGION_LOCKED", "当前国家已锁定，请先解除锁定")
    if row is None:
        row = UserRegionPref(
            user_id=user.id,
            region_code=body.region_code,
            source=body.source,
            locked=body.locked,
            consent_id=body.consent_id,
            browse_region_code=body.browse_region_code,
            updated_at=now,
        )
        session.add(row)
    else:
        row.region_code = body.region_code
        row.source = body.source
        row.consent_id = body.consent_id
        if body.browse_region_code is not None:
            row.browse_region_code = body.browse_region_code or None
        if body.locked:
            row.locked = True
        row.updated_at = now
    write_audit(session, user.id, "region.set", "user", user.id)
    session.commit()
    station_name, station_city = _station(session, user)
    open_list = [{"code": code, "name": name, "city": city} for code, (name, city) in open_regions(session).items()]
    return {
        "region_code": row.region_code,
        "source": row.source,
        "locked": row.locked,
        "consent_id": row.consent_id,
        "browse_region_code": row.browse_region_code,
        "roaming": is_roaming(session, user),
        "station_name": station_name,
        "station_city": station_city,
        "updated_at": row.updated_at.isoformat(),
        "open_regions": open_list,
    }


def export_account(user: User, session: Session) -> dict[str, object]:
    """这个人的全部个人数据。前台不再提供自助导出；用户来要时由超级管理员在后台导出（admin_ops.export_user_data）。"""
    subscriptions = session.scalars(select(ChannelSubscription).where(ChannelSubscription.user_id == user.id)).all()
    posts = session.scalars(select(Content).where(Content.author_id == user.id)).all()
    consents = session.scalars(select(ConsentRecord).where(ConsentRecord.user_id == user.id)).all()
    comments = session.scalars(select(RoomComment).where(RoomComment.author_id == user.id).order_by(RoomComment.created_at)).all()
    messages = session.scalars(select(DmMessage).where(DmMessage.sender_id == user.id).order_by(DmMessage.created_at)).all()
    contacts = dict(
        session.execute(select(ListingExt.content_id, ListingExt.contact).where(ListingExt.content_id.in_([row.id for row in posts] or [""]))).all()
    )
    return {
        "user": {
            "email": user.email,
            "display_name": user.display_name,
            "handle": user.handle or "",
            "avatar_tone": user.avatar_tone,
            "bio": user.bio or "",
            "phone": user.phone,
        },
        "subscriptions": [row.channel_id for row in subscriptions],
        "posts": [
            {
                "content_id": row.id,
                "title": row.title,
                "status": row.status,
                "body": row.body or row.summary or "",
                "contact": contacts.get(row.id, ""),  # 分类信息里留的联系方式
                "created_at": row.created_at.isoformat(),
            }
            for row in posts
        ],
        "comments": [{"body": row.body, "created_at": row.created_at.isoformat()} for row in comments],
        "messages": [{"body": row.body, "created_at": row.created_at.isoformat()} for row in messages],  # 只有本人发出的
        "consents": [{"purpose": row.purpose, "version": row.version, "granted": row.granted} for row in consents],
    }


@router.delete("")
def erase_account(user: User = Depends(current_user), session: Session = Depends(get_db)) -> dict[str, str]:
    now = utcnow()
    user.deleted_at = now
    user.status = "deleted"
    user.email = f"erased-{user.id}@deleted.local"
    user.password_hash = ""
    user.phone = None
    user.display_name = "已注销"
    user.handle = None
    user.bio = None
    user.avatar_key = None  # 图片文件在下面和其他上传一起删
    # 后台权限也收回：注销后的账号在后台改不了权限（按「用户不存在」处理），留着就永远撤不掉
    user.is_admin = False
    user.is_super = False
    user.totp_secret = None
    subscriptions = session.scalars(select(ChannelSubscription).where(ChannelSubscription.user_id == user.id)).all()
    for subscription in subscriptions:
        channel = session.get(Channel, subscription.channel_id)
        if channel is not None:
            channel.bump_subscribers(-1)
        session.delete(subscription)
    # 隐私政策承诺「删除或匿名化」：帖子不只是标成已删除，正文和分类信息里的联系方式（电话、微信）也抹掉，
    # 不然它们原样留在数据库和备份里。以前自己删过的帖子同样处理。
    posts = session.scalars(select(Content).where(Content.author_id == user.id)).all()
    for post in posts:
        if post.deleted_at is None:
            post.status = "deleted"
            post.deleted_at = now
        post.title = "已注销用户的内容"
        post.summary = None
        post.body = None
        post.keywords_json = "[]"
    session.execute(
        update(ListingExt).where(ListingExt.content_id.in_([post.id for post in posts] or [""])).values(contact="", area="")
    )
    # 留言也是这个人写的内容：一并移除（和后台「下架全部」同样处理），文字也抹掉
    session.execute(
        update(RoomComment)
        .where(RoomComment.author_id == user.id, RoomComment.removed_at.is_(None))
        .values(status="removed", removed_at=now)
    )
    session.execute(update(RoomComment).where(RoomComment.author_id == user.id).values(body=""))
    # 页面承诺「删除资料、帖子和房间」：自建房间下线，上传的文件连磁盘一起删
    # （不删的话文件仍留在服务器，知道原链接的人还能打开）。
    for room in session.scalars(select(Channel).where(Channel.owner_id == user.id, Channel.kind == "room")).all():
        room.is_active = False
        if room.review_status == "pending":
            room.review_status = "rejected"  # 还没审过的房间撤掉：留在后台待审队列里，管理员一点「通过」就会以「已注销」的名义上线
    # 刷新令牌记录也一并清掉：不删的话它们带着用户 id 一直留到有人拿来刷新为止。
    session.execute(delete(RefreshSession).where(RefreshSession.user_id == user.id))
    # 关注 / 拉黑关系也删：账号只是软删除，外键不会连带删，不删的话别人的关注者数里还算着这个人
    session.execute(delete(UserFollow).where(or_(UserFollow.user_id == user.id, UserFollow.target_id == user.id)))
    session.execute(delete(UserBlock).where(or_(UserBlock.user_id == user.id, UserBlock.target_id == user.id)))
    for upload in session.scalars(select(UploadObject).where(UploadObject.owner_id == user.id)).all():
        delete_object(upload.key)
        session.delete(upload)
    write_audit(session, user.id, "account.erase", "user", user.id)
    session.commit()
    return {"status": "erased"}
