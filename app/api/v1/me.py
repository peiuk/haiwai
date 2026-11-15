import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel, field_validator
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.api.v1.auth import current_user, optional_user
from app.api.v1.uploads import upload_root
from app.core.audit import write_audit
from app.core.db import get_db
from app.core.errors import APIError
from app.core.pagination import decode_cursor, encode_cursor, paginate_rows
from app.core.regions import OPEN_REGIONS, is_open_region
from app.feed import build_following_feed, paginate_feed
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
    ModerationCase,
    Notification,
    RefreshSession,
    UploadObject,
    User,
    UserBlock,
    RegionOpenRequest,
    UserRegionPref,
    utcnow,
)

router = APIRouter(prefix="/me")


@router.get("")
def my_profile(user: User = Depends(current_user)) -> dict[str, str]:
    return {
        "user_id": user.id,
        "display_name": user.display_name,
        "handle": user.handle or "",
        "avatar_tone": user.avatar_tone,
        "city_label": user.city_label or "",
        "script_pref": user.script_pref,
        "phone": user.phone or "",
    }


class ProfilePatch(BaseModel):
    display_name: str | None = None
    handle: str | None = None
    avatar_tone: str | None = None
    city_label: str | None = None

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


@router.patch("")
def update_profile(
    body: ProfilePatch,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    if body.display_name is not None:
        user.display_name = body.display_name
    if body.handle is not None and body.handle != user.handle:
        taken = session.scalar(select(User.id).where(User.handle == body.handle, User.id != user.id))
        if taken is not None:
            raise APIError(409, "DUPLICATE_HANDLE", "这个账号名已经有人用了")
        user.handle = body.handle
    if body.avatar_tone is not None:
        user.avatar_tone = body.avatar_tone
    if body.city_label is not None:
        user.city_label = body.city_label or None
    session.commit()
    return my_profile(user)


def _content_paused(session: Session, user: User, content_id: str) -> bool:
    placements = session.scalars(select(ChannelItem).where(ChannelItem.content_id == content_id)).all()
    channels = [channel for row in placements if (channel := session.get(Channel, row.channel_id)) is not None]
    if not channels:
        return False
    return all(country_blocked(session, user, channel) for channel in channels)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _mark_seen_divider(items: list[dict[str, object]], seen_at: datetime | None) -> int:
    fresh_count = 0
    placed = False
    for item in items:
        added = _as_utc(datetime.fromisoformat(str(item["added_at"])))
        fresh = not item.get("pinned") and seen_at is not None and added > _as_utc(seen_at)
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
    subscription = session.get(ChannelSubscription, (user.id, channel.id))
    if subscription is None:
        session.add(ChannelSubscription(user_id=user.id, channel_id=channel.id))
        channel.subscriber_count += 1
        session.commit()
    return {"joined": True, "subscriber_count": channel.subscriber_count}


def _unread(session: Session, subscription: ChannelSubscription) -> int:
    count = session.scalar(
        select(func.count())
        .select_from(ChannelItem)
        .join(Content, Content.id == ChannelItem.content_id)
        .where(
            ChannelItem.channel_id == subscription.channel_id,
            Content.status == "published",
            Content.deleted_at.is_(None),
            ChannelItem.added_at > subscription.last_read_at,
        )
    )
    return int(count or 0)


@router.get("/subscriptions")
def list_subscriptions(
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    rows = session.scalars(select(ChannelSubscription).where(ChannelSubscription.user_id == user.id)).all()
    items: list[dict[str, object]] = []
    paused = 0
    for subscription in rows:
        channel = session.get(Channel, subscription.channel_id)
        if channel is None:
            continue
        count = _unread(session, subscription)
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
    if channel is not None and channel.subscriber_count > 0:
        channel.subscriber_count -= 1
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
    threads = session.scalars(
        select(DmThread).where(or_(DmThread.user_low == user.id, DmThread.user_high == user.id))
    ).all()
    messages = 0
    for thread in threads:
        other_id = thread.user_high if thread.user_low == user.id else thread.user_low
        if session.get(UserBlock, (user.id, other_id)) is not None or session.get(UserBlock, (other_id, user.id)) is not None:
            continue
        messages += int(
            session.scalar(
                select(func.count())
                .select_from(DmMessage)
                .where(
                    DmMessage.thread_id == thread.id,
                    DmMessage.sender_id != user.id,
                    DmMessage.read_at.is_(None),
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
    rows = list(
        session.scalars(
            select(Notification).where(Notification.user_id == user.id).order_by(Notification.created_at.desc())
        ).all()
    )
    unread = sum(1 for row in rows if row.read_at is None)
    bounded = min(max(limit, 1), 50)
    page, next_cursor = paginate_rows(rows, cursor, bounded, "id", "created_at")
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


@router.post("/notifications/read")
def read_notifications(user: User = Depends(current_user), session: Session = Depends(get_db)) -> dict[str, int]:
    rows = session.scalars(
        select(Notification).where(Notification.user_id == user.id, Notification.read_at.is_(None))
    ).all()
    now = utcnow()
    for row in rows:
        row.read_at = now
    session.commit()
    return {"marked": len(rows)}


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
def my_posts(user: User = Depends(current_user), session: Session = Depends(get_db)) -> dict[str, list[dict[str, str | None]]]:
    rows = session.scalars(
        select(Content)
        .where(Content.author_id == user.id, Content.deleted_at.is_(None))
        .order_by(Content.created_at.desc())
    ).all()
    return {
        "items": [
            {"content_id": row.id, "title": row.title, "status": row.status, "summary": row.summary}
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
    session.commit()
    return {"seen_at": user.feed_seen_at.isoformat()}


class ScriptBody(BaseModel):
    script_pref: str

    @field_validator("script_pref")
    @classmethod
    def known_script(cls, value: str) -> str:
        if value not in {"hans", "hant"}:
            raise ValueError("简繁偏好只能是 hans 或 hant")
        return value


@router.get("/script")
def get_script(user: User = Depends(current_user)) -> dict[str, str]:
    return {"script_pref": user.script_pref}


@router.put("/script")
def update_script(
    body: ScriptBody,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    user.script_pref = body.script_pref
    session.commit()
    return {"script_pref": user.script_pref}


class RegionBody(BaseModel):
    region_code: str
    source: str = "manual"
    consent_id: str | None = None
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
        if code == "":
            return ""
        if code not in OPEN_REGIONS:
            raise ValueError("只能浏览已开通的国家")
        return code


_STATIONS = OPEN_REGIONS


def _station(session: Session, user: User) -> tuple[str, str]:
    if not is_roaming(session, user):
        return "", ""
    pref = session.get(UserRegionPref, user.id)
    code = pref.browse_region_code if pref is not None and pref.browse_region_code else ""
    return _STATIONS.get(code, ("", ""))


@router.get("/regions")
def get_region(user: User = Depends(current_user), session: Session = Depends(get_db)) -> dict[str, object]:
    row = session.get(UserRegionPref, user.id)
    station_name, station_city = _station(session, user)
    open_list = [{"code": code, "name": name, "city": city} for code, (name, city) in OPEN_REGIONS.items()]
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
    open_list = [{"code": code, "name": name, "city": city} for code, (name, city) in OPEN_REGIONS.items()]
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


@router.get("/export")
def export_account(user: User = Depends(current_user), session: Session = Depends(get_db)) -> dict[str, object]:
    subscriptions = session.scalars(select(ChannelSubscription).where(ChannelSubscription.user_id == user.id)).all()
    posts = session.scalars(select(Content).where(Content.author_id == user.id)).all()
    consents = session.scalars(select(ConsentRecord).where(ConsentRecord.user_id == user.id)).all()
    return {
        "user": {
            "email": user.email,
            "display_name": user.display_name,
            "handle": user.handle or "",
            "avatar_tone": user.avatar_tone,
            "phone": user.phone,
        },
        "subscriptions": [row.channel_id for row in subscriptions],
        "posts": [{"content_id": row.id, "title": row.title, "status": row.status} for row in posts],
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
    subscriptions = session.scalars(select(ChannelSubscription).where(ChannelSubscription.user_id == user.id)).all()
    for subscription in subscriptions:
        channel = session.get(Channel, subscription.channel_id)
        if channel is not None and channel.subscriber_count > 0:
            channel.subscriber_count -= 1
        session.delete(subscription)
    posts = session.scalars(select(Content).where(Content.author_id == user.id, Content.deleted_at.is_(None))).all()
    for post in posts:
        post.status = "deleted"
        post.deleted_at = now
    # 页面承诺「删除资料、帖子和房间」：自建房间下线，上传的文件连磁盘一起删
    # （不删的话文件仍留在服务器，知道原链接的人还能打开）。
    for room in session.scalars(select(Channel).where(Channel.owner_id == user.id, Channel.kind == "room")).all():
        room.is_active = False
    # 刷新令牌记录也一并清掉：不删的话它们带着用户 id 一直留到有人拿来刷新为止。
    session.execute(delete(RefreshSession).where(RefreshSession.user_id == user.id))
    root = upload_root()
    for upload in session.scalars(select(UploadObject).where(UploadObject.owner_id == user.id)).all():
        (root / upload.key).unlink(missing_ok=True)
        session.delete(upload)
    write_audit(session, user.id, "account.erase", "user", user.id)
    session.commit()
    return {"status": "erased"}
