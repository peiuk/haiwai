import json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, field_validator
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.api.v1.auth import current_user, optional_user, require_verified_phone
from app.api.v1.uploads import owned_upload
from app.core.audit import write_audit
from app.core.db import get_db
from app.core.errors import APIError
from app.core.pagination import decode_cursor, encode_cursor, parse_added_at
from app.core.regions import region_name
from app.guard import first_status
from app.feed import MAX_LISTING_IMAGES, author_names, card_extras, image_keys_of, reaction_flags, repost_context
from app.keywords import clean_city_topic, dump_keywords, resolve_keywords
from app.models import Channel, ChannelItem, ChannelSubscription, ContactView, Content, ContentReaction, ListingExt, User, new_id, utcnow
from app.recommend import country_blocked, effective_region, is_roaming

router = APIRouter()
CONTACT_DAILY_LIMIT = 5
_ATTRS = {
    "rent": {"roomType", "moveIn", "bills", "deposit", "minTerm"},
    "sale": {"roomType"},
    "commercial": {"roomType"},
    "secondhand": {"condition", "pickup"},
    "job": {"jobType", "hours"},
}
_UNITS = {
    "rent": {"月", "周"},
    "sale": {"总价"},
    "commercial": {"月", "总价"},
    "secondhand": {""},
    "job": {"小时", "月", "年"},
}
_CURRENCY = {"UK": "GBP", "JP": "JPY", "CA": "CAD"}


class ListingBody(BaseModel):
    channel_id: str
    title: str
    body: str
    category: str
    kind: str
    area: str
    price_amount: str
    price_unit: str = ""
    contact: str
    attrs: dict[str, str] = {}
    keywords: list[str] = []
    city_topic: str | None = None
    keyword_source: str | None = None
    # image_key 兼容旧客户端的单图提交；新客户端优先使用 image_keys（最多 4 张）。
    image_key: str | None = None
    image_keys: list[str] = []

    @field_validator("image_keys")
    @classmethod
    def bounded_images(cls, value: list[str]) -> list[str]:
        keys = [key for key in dict.fromkeys(value) if key]
        if len(keys) > MAX_LISTING_IMAGES:
            raise ValueError(f"分类信息最多上传 {MAX_LISTING_IMAGES} 张图片")
        return keys

    @field_validator("keyword_source")
    @classmethod
    def known_keyword_source(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if value not in {"ai_auto", "user"}:
            raise ValueError("关键词来源不正确")
        return value

    @field_validator("city_topic")
    @classmethod
    def city_topic_token(cls, value: str | None) -> str | None:
        return clean_city_topic(value)

    @field_validator("title", "body", "area", "price_amount", "contact")
    @classmethod
    def nonempty(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("必填项不能为空")
        return text

    @field_validator("category")
    @classmethod
    def known_category(cls, value: str) -> str:
        if value not in {"房产", "市场", "招聘"}:
            raise ValueError("分类不正确")
        return value


def _kind_for(body: ListingBody) -> str:
    expected = {"房产": {"rent", "sale", "commercial"}, "市场": {"secondhand"}, "招聘": {"job"}}
    if body.kind not in expected[body.category]:
        raise APIError(400, "VALIDATION_FAILED", "分类和类型不匹配")
    if body.price_unit not in _UNITS[body.kind]:
        raise APIError(400, "VALIDATION_FAILED", "价格单位不正确")
    return body.kind


def _currency(channel: Channel, user_region: str) -> str:
    region = channel.region_code
    if region == "GLOBAL":
        region = user_region
    return _CURRENCY.get(region, "¤")


def _listing_expired(expires_at: datetime | None) -> bool:
    if expires_at is None:
        return False
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at < datetime.now(timezone.utc)


def _author_card(session: Session, content: Content) -> dict[str, str]:
    author = session.get(User, content.author_id) if content.author_id else None
    return {
        "author_id": content.author_id or "",
        "author_name": author.display_name if author else "",
        "author_handle": author.handle or "" if author else "",
    }


def _public_listing(content: Content, ext: ListingExt, channel: Channel) -> dict[str, object]:
    return {
        "content_id": content.id,
        "title": content.title,
        "summary": content.summary,
        "category": ext.category,
        "kind": ext.kind,
        "area": ext.area,
        "price_amount": ext.price_amount,
        "price_unit": ext.price_unit or "",
        "currency": ext.currency,
        "attrs": json.loads(ext.attrs_json or "{}"),
        "closed_reason": ext.closed_reason,
        "expires_at": content.expires_at.isoformat() if content.expires_at else None,
        "expired": _listing_expired(content.expires_at),
        "channel_id": channel.id,
        "channel_name": channel.name_hans,
        "certified": content.status == "published",
        "source_name": content.source_name or "",
        "licence_ref": content.licence_ref or "",
        "region_code": channel.region_code,
        "image_keys": image_keys_of(content),
        "placeholder": False,
    }


def _visible(channel: Channel, region: str) -> bool:
    if channel.region_code == "GLOBAL":
        return True
    return channel.region_code == region


@router.post("/listings")
def create_listing(
    body: ListingBody,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    require_verified_phone(user, "发布")
    if is_roaming(session, user):
        raise APIError(403, "ROAMING_READONLY", "跨国漫游下仅供浏览，发帖请切换至本地")
    kind = _kind_for(body)
    channel = session.get(Channel, body.channel_id)
    if channel is None or not channel.is_active or channel.kind == "room":
        raise APIError(400, "CHANNEL_CATEGORY_MISMATCH", "分类信息只能发到对应的官方频道")
    if channel.category != body.category:
        raise APIError(400, "CHANNEL_CATEGORY_MISMATCH", "分类和频道不一致")
    if country_blocked(session, user, channel):
        raise APIError(403, "REGION_BLOCKED", "当前国家看不到这个频道")
    allowed = _ATTRS[kind]
    attrs = {key: value for key, value in body.attrs.items() if key in allowed and value.strip()}
    keys = list(body.image_keys)
    if not keys and body.image_key:
        keys = [body.image_key]
    keys = list(dict.fromkeys(keys))[:MAX_LISTING_IMAGES]
    for key in keys:
        owned_upload(session, user, key)
    now = utcnow()
    words, source = resolve_keywords(body.keywords, body.title, body.body, body.keyword_source, body.category)
    status = first_status(session, "listing", body.title, body.body)
    content = Content(
        type="listing",
        status=status,
        author_id=user.id,
        title=body.title,
        summary=body.body[:500],
        body=body.body,
        keywords_json=dump_keywords(words),
        keyword_source=source,
        city_topic=body.city_topic,
        source_name=user.display_name,
        image_key=keys[0] if keys else None,
        image_keys_json=json.dumps(keys),
        expires_at=now + timedelta(days=30),
        published_at=now if status == "published" else None,
    )
    session.add(content)
    session.flush()
    session.add(
        ListingExt(
            content_id=content.id,
            category=body.category,
            kind=kind,
            area=body.area,
            price_amount=body.price_amount,
            price_unit=body.price_unit or None,
            currency=_currency(channel, effective_region(session, user)),
            contact=body.contact,
            attrs_json=json.dumps(attrs, ensure_ascii=False),
        )
    )
    session.add(ChannelItem(channel_id=channel.id, content_id=content.id, added_at=now))
    write_audit(session, user.id, "listing.create", "content", content.id)
    session.commit()
    return {
        "content_id": content.id,
        "status": content.status,
        "type": content.type,
        "keywords": words,
        "keyword_source": source,
        "city_topic": content.city_topic or "",
    }


@router.get("/listings/{content_id}")
def get_listing(
    content_id: str,
    user: User | None = Depends(optional_user),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    content = session.get(Content, content_id)
    ext = session.get(ListingExt, content_id)
    if content is None or ext is None or content.deleted_at is not None or content.type != "listing":
        raise APIError(404, "CONTENT_NOT_FOUND", "内容不存在")
    item = session.scalar(select(ChannelItem).where(ChannelItem.content_id == content.id))
    channel = session.get(Channel, item.channel_id) if item else None
    if channel is None:
        raise APIError(404, "CONTENT_NOT_FOUND", "内容不存在")
    if content.status not in {"published", "withdrawn"} and (user is None or content.author_id != user.id):
        raise APIError(404, "CONTENT_NOT_FOUND", "内容不存在")
    region = effective_region(session, user) if user else "GLOBAL"
    if not _visible(channel, region):
        return {"content_id": content.id, "placeholder": True, "title": "这条信息不在当前国家"}
    payload = _public_listing(content, ext, channel)
    payload.update(_author_card(session, content))
    payload["status"] = content.status
    payload["contact_views_limit"] = CONTACT_DAILY_LIMIT
    payload["contact_views_remaining"] = _remaining(session, user.id) if user is not None else None
    return payload


def _remaining(session: Session, user_id: str) -> int:
    today = utcnow().astimezone(ZoneInfo("Europe/London")).date().isoformat()
    used = session.scalar(
        select(func.count()).select_from(ContactView).where(ContactView.user_id == user_id, ContactView.viewed_on == today)
    )
    return max(0, CONTACT_DAILY_LIMIT - int(used or 0))


@router.post("/listings/{content_id}/contact")
def view_contact(
    content_id: str,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    content = session.get(Content, content_id)
    ext = session.get(ListingExt, content_id)
    if content is None or ext is None or content.status != "published" or content.deleted_at is not None:
        raise APIError(404, "CONTENT_NOT_FOUND", "内容不存在")
    if ext.closed_reason:
        raise APIError(410, "LISTING_CLOSED", "该信息已结案，联系方式已关闭")
    expires = content.expires_at
    if expires is not None and expires.tzinfo is None:
        expires = expires.replace(tzinfo=utcnow().tzinfo)
    if expires is not None and expires < utcnow():
        raise APIError(410, "LISTING_EXPIRED", "这条信息已过期")
    item = session.scalar(select(ChannelItem).where(ChannelItem.content_id == content.id))
    channel = session.get(Channel, item.channel_id) if item else None
    if channel is None or not _visible(channel, effective_region(session, user)):
        raise APIError(404, "CONTENT_NOT_FOUND", "这条信息不在当前国家")
    remaining = _remaining(session, user.id)
    if remaining <= 0:
        raise APIError(429, "CONTACT_LIMIT", "今日查询次数已达上限（5次），可通过私信咨询联系对方")
    today = utcnow().astimezone(ZoneInfo("Europe/London")).date().isoformat()
    session.add(ContactView(id=new_id(), user_id=user.id, content_id=content.id, viewed_on=today))
    write_audit(session, user.id, "listing.contact", "content", content.id)
    session.commit()
    return {"contact": ext.contact, "contact_views_remaining": remaining - 1}


class CloseBody(BaseModel):
    reason: str

    @field_validator("reason")
    @classmethod
    def known_reason(cls, value: str) -> str:
        if value not in {"rented", "sold", "withdrawn"}:
            raise ValueError("下架原因不正确")
        return value


@router.post("/listings/{content_id}/close")
def close_listing(
    content_id: str,
    body: CloseBody,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    content, ext = _owned_listing(session, content_id, user)
    ext.closed_reason = body.reason
    ext.closed_at = utcnow()
    content.status = "withdrawn"
    write_audit(session, user.id, "listing.close", "content", content.id)
    session.commit()
    return {"content_id": content.id, "closed_reason": body.reason}


@router.post("/listings/{content_id}/renew")
def renew_listing(
    content_id: str,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    content, ext = _owned_listing(session, content_id, user)
    expires = content.expires_at
    if expires is not None and expires.tzinfo is None:
        expires = expires.replace(tzinfo=utcnow().tzinfo)
    soon = expires is None or expires <= utcnow() + timedelta(days=3)
    if not soon and not ext.closed_reason:
        raise APIError(409, "LISTING_NOT_DUE", "还没到可以刷新的时间")
    now = utcnow()
    content.expires_at = now + timedelta(days=30)
    content.status = "published"
    content.published_at = now
    ext.closed_reason = None
    ext.closed_at = None
    item = session.scalar(select(ChannelItem).where(ChannelItem.content_id == content.id))
    if item is not None:
        item.added_at = now
    write_audit(session, user.id, "listing.renew", "content", content.id)
    session.commit()
    return {"content_id": content.id, "expires_at": content.expires_at.isoformat()}


def _owned_listing(session: Session, content_id: str, user: User) -> tuple[Content, ListingExt]:
    content = session.get(Content, content_id)
    ext = session.get(ListingExt, content_id)
    if content is None or ext is None or content.author_id != user.id or content.deleted_at is not None:
        raise APIError(404, "CONTENT_NOT_FOUND", "内容不存在")
    # 只有上过线的信息能结案 / 刷新：否则被拒或待审的可以「结案再刷新」绕过审核直接发布
    if content.status not in {"published", "withdrawn"}:
        raise APIError(409, "LISTING_NOT_LIVE", "这条信息还没通过审核，不能结案或刷新")
    return content, ext


@router.get("/discover/listings")
def discover_listings(
    category: str | None = None,
    region_filter: str | None = Query(default=None, alias="region"),
    user: User | None = Depends(optional_user),
    session: Session = Depends(get_db),
) -> dict[str, list[dict[str, object]]]:
    region = effective_region(session, user) if user else "GLOBAL"
    # 跟发现页内容流用同一组筛选：选了「招聘」就不该还冒出房源。新发布的排前面。
    query = (
        select(Content, Channel, ListingExt)
        .join(ListingExt, ListingExt.content_id == Content.id)
        .join(ChannelItem, and_(ChannelItem.content_id == Content.id, ChannelItem.origin_room_id.is_(None)))
        .join(Channel, Channel.id == ChannelItem.channel_id)
        .where(
            Content.type == "listing",
            Content.status == "published",
            Content.deleted_at.is_(None),
            ListingExt.closed_reason.is_(None),
            Channel.region_code.in_(("GLOBAL", region)),  # 与 _visible 相同
        )
        .order_by(Content.created_at.desc())
    )
    if category:
        query = query.where(Channel.category == category)
    wanted_region = (region_filter or "").upper()
    if wanted_region:
        query = query.where(Channel.region_code == wanted_region)
    items: list[dict[str, object]] = []
    seen: set[str] = set()
    now = utcnow()
    for content, channel, ext in session.execute(query).all():
        if content.id in seen:
            continue
        expires = content.expires_at
        if expires is not None and expires.tzinfo is None:
            expires = expires.replace(tzinfo=now.tzinfo)
        if expires is not None and expires < now:
            continue
        seen.add(content.id)
        card = _public_listing(content, ext, channel)
        card.update(_author_card(session, content))
        items.append(card)
        if len(items) >= 4:
            break
    return {"items": items}


@router.get("/discover/items")
def discover_items(
    category: str | None = None,
    region_filter: str | None = Query(default=None, alias="region"),
    limit: int = 20,
    cursor: str | None = None,
    user: User | None = Depends(optional_user),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    region = effective_region(session, user) if user else "GLOBAL"
    bounded = min(max(limit, 1), 50)
    # 过滤、计数、分页都交给数据库：原来每次请求把全部频道条目读进内存再筛，内容越多越慢，且游客就能触发。
    visible_where = [
        Content.status == "published",
        Content.deleted_at.is_(None),
        Content.type.not_in(("embed", "repost")),
        # 分类信息和频道动态合在一个列表里：只收没过期、没结案的。
        or_(
            Content.type != "listing",
            and_(
                Content.expires_at > utcnow(),
                Content.id.not_in(select(ListingExt.content_id).where(ListingExt.closed_reason.is_not(None))),
            ),
        ),
        ChannelItem.origin_room_id.is_(None),
        Channel.kind != "room",
        Channel.is_active.is_(True),
        Channel.region_code.in_(("GLOBAL", region)),  # 与 _visible 相同：国际频道 + 当前国家
    ]

    def scoped(*columns):
        return (
            select(*columns)
            .select_from(ChannelItem)
            .join(Content, Content.id == ChannelItem.content_id)
            .join(Channel, Channel.id == ChannelItem.channel_id)
        )

    categories = sorted(
        value for value in session.scalars(scoped(Channel.category).where(*visible_where).distinct()).all() if value
    )
    # 地区筛选只能在「用户本来就看得到」的范围里再收窄（国际 / 当前国家），不会放宽可见范围。
    wanted_region = (region_filter or "").upper()
    filtered_where = list(visible_where)
    if category:
        filtered_where.append(Channel.category == category)
    if wanted_region:
        filtered_where.append(Channel.region_code == wanted_region)
    # 同一条内容可能挂在多个频道：按内容去重，每条取它在筛选范围内最新的那次收录；
    # 按 (最新收录时间, 内容 id) 做游标分页，翻页不重复、不遗漏。
    latest = func.max(ChannelItem.added_at).label("latest")
    grouped = (
        scoped(ChannelItem.content_id.label("content_id"), latest)
        .where(*filtered_where)
        .group_by(ChannelItem.content_id)
        .subquery()
    )
    updated_count = session.scalar(
        select(func.count()).select_from(grouped).where(grouped.c.latest >= utcnow() - timedelta(days=7))
    ) or 0
    ordered = select(grouped.c.content_id, grouped.c.latest).order_by(grouped.c.latest.desc(), grouped.c.content_id.desc())
    parts = decode_cursor(cursor) if cursor else None
    after_at = parse_added_at(parts[0]) if parts and len(parts) == 2 else None
    if parts and after_at is not None:
        ordered = ordered.where(
            or_(grouped.c.latest < after_at, and_(grouped.c.latest == after_at, grouped.c.content_id < parts[1]))
        )
    rows = session.execute(ordered.limit(bounded + 1)).all()
    next_cursor = (
        encode_cursor(rows[bounded - 1].latest.isoformat(), rows[bounded - 1].content_id) if len(rows) > bounded else None
    )
    ids = [row.content_id for row in rows[:bounded]]
    newest: dict[str, ChannelItem] = {}
    for candidate in session.scalars(
        scoped(ChannelItem)
        .where(*filtered_where, ChannelItem.content_id.in_(ids))
        .options(joinedload(ChannelItem.channel), joinedload(ChannelItem.content))
    ).unique().all():
        kept = newest.get(candidate.content_id)
        if kept is None or candidate.added_at > kept.added_at:
            newest[candidate.content_id] = candidate
    page = [newest[content_id] for content_id in ids if content_id in newest]
    joined: set[str] = set()
    if user is not None:
        joined = set(
            session.scalars(select(ChannelSubscription.channel_id).where(ChannelSubscription.user_id == user.id)).all()
        )
    authors = author_names(session, [item.content.author_id for item in page])
    # 登录用户带上自己的点赞 / 收藏 / 转发状态（与推荐流一致），游客全为 False。
    user_id = user.id if user else None
    flags = reaction_flags(session, user_id, [item.content_id for item in page])
    _, reposted_ids = repost_context(session, user_id, [item.content for item in page])
    listing_ids = [item.content_id for item in page if item.content.type == "listing"]
    exts = {
        row.content_id: row
        for row in session.scalars(select(ListingExt).where(ListingExt.content_id.in_(listing_ids))).all()
    } if listing_ids else {}
    items: list[dict[str, object]] = []
    for item in page:
        channel = item.channel
        content = item.content
        ext = exts.get(content.id)
        items.append(
            {
                # 分类信息带上卡片所需的全部字段（价格、地区、到期等），前端用分类信息卡渲染。
                "listing": {**_public_listing(content, ext, channel), **_author_card(session, content)} if ext else None,
                "content_id": content.id,
                "title": content.title,
                "summary": content.summary,
                "source_name": content.source_name or "",
                "licence_ref": content.licence_ref or "",
                "canonical_url": content.canonical_url,
                "channel_id": channel.id,
                "channel_name": channel.name_hans,
                "channel_certified": channel.certified,
                "is_joined": channel.id in joined,
                "category": channel.category,
                "added_at": item.added_at.isoformat(),
                **card_extras(content, None, authors.get(content.author_id or "", ("", ""))),
                "liked": flags.get(item.content_id, (False, False))[0],
                "favorited": flags.get(item.content_id, (False, False))[1],
                "reposted": item.content_id in reposted_ids,
            }
        )
    return {
        "items": items,
        "updated_count": updated_count,
        "categories": categories,
        # 当前浏览国家，供前端渲染「全部地区 / 国际 / 当前国家」筛选 chip。
        "region": {"code": region, "name": region_name(session, region)},
        "next_cursor": next_cursor,
    }


# ---- 首页右栏：最新新闻 / 今日最关注 / 本周点击最多 ----


def _rail_card(
    session: Session,
    content: Content,
    channel: Channel,
) -> dict[str, object]:
    """构造右栏条目卡片（精简字段，供首页右栏展示与跳转）。"""
    card: dict[str, object] = {
        "content_id": content.id,
        "title": content.title,
        "summary": content.summary,
        "source_name": content.source_name or "",
        "canonical_url": content.canonical_url,
        "channel_id": channel.id if channel else None,
        "channel_name": channel.name_hans if channel else "",
        "type": content.type,
        "published_at": content.published_at.isoformat() if content.published_at else None,
        "view_count": content.view_count or 0,
    }
    author = session.get(User, content.author_id) if content.author_id else None
    card["author_name"] = author.display_name if author else ""
    return card


def _dt_key(value: datetime | None) -> float:
    """把可能 naive/aware 混用的 datetime 归一为 UTC 时间戳，用于安全排序与比较。"""
    if value is None:
        return 0.0
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.timestamp()


def _published_rows(
    session: Session,
    region: str,
    since: datetime,
) -> list[tuple[Content, Channel]]:
    """取某时间点之后发布的可见内容（含频道归属），排除 listing/embed/repost。"""
    rows = session.scalars(
        select(ChannelItem)
        .join(Content, Content.id == ChannelItem.content_id)
        .join(Channel, Channel.id == ChannelItem.channel_id)
        .where(
            Content.status == "published",
            Content.deleted_at.is_(None),
            Content.type.notin_(["listing", "embed", "repost"]),
            ChannelItem.origin_room_id.is_(None),
            # 时间窗放进 SQL：原来每次首页访问都把全部收录读进内存再按日期筛。
            func.coalesce(Content.published_at, Content.created_at) >= since,
        )
        .options(joinedload(ChannelItem.content), joinedload(ChannelItem.channel))
    ).unique().all()
    since_key = _dt_key(since)
    pairs: list[tuple[Content, Channel]] = []
    for item in rows:
        if not _visible(item.channel, region):
            continue
        published = _dt_key(item.content.published_at) or _dt_key(item.content.created_at)
        if published >= since_key:
            pairs.append((item.content, item.channel))
    return pairs


def _heat(content: Content, liked: int, favorited: int) -> int:
    """热度分：浏览 1 分、点赞 3 分、收藏 5 分（收藏意图最强，权重最高）。"""
    return (content.view_count or 0) + liked * 3 + favorited * 5


@router.get("/discover/home-rail")
def home_rail(
    user: User | None = Depends(optional_user),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    region = effective_region(session, user) if user else "GLOBAL"
    now = utcnow()

    # 1) 最新新闻：type=news 按发布时间倒序，最多 6 条（按内容去重，一条新闻可能归属多个频道）。
    news_rows = session.scalars(
        select(ChannelItem)
        .join(Content, Content.id == ChannelItem.content_id)
        .join(Channel, Channel.id == ChannelItem.channel_id)
        .where(
            Content.type == "news",
            Content.status == "published",
            Content.deleted_at.is_(None),
            ChannelItem.origin_room_id.is_(None),
        )
        .options(joinedload(ChannelItem.content), joinedload(ChannelItem.channel))
        .order_by(Content.published_at.desc())
        # 只要 6 条，多取一些给去重和地区过滤留余量。
        # shortcut: 若可见地区的新闻全排在 60 条之外会少于 6 条，地区频道多起来后把地区条件也放进 SQL。
        .limit(60)
    ).unique().all()
    news: list[dict[str, object]] = []
    seen_news: set[str] = set()
    for item in news_rows:
        if not _visible(item.channel, region):
            continue
        if item.content_id in seen_news:
            continue
        seen_news.add(item.content_id)
        news.append(_rail_card(session, item.content, item.channel))
        if len(news) >= 6:
            break

    # 2) 今日最关注 + 3) 本周点击最多：按时间窗聚合，热度分排序。
    today_cutoff = now - timedelta(days=1)
    week_cutoff = now - timedelta(days=7)

    def ranked(since: datetime, limit: int) -> list[dict[str, object]]:
        pairs = _published_rows(session, region, since)
        # 同一条内容可能归属多个频道，按 content 去重（保留热度最高的一份）。
        best: dict[str, tuple[int, Content, Channel]] = {}
        ids = [content.id for content, _channel in pairs]
        reactions: dict[str, tuple[int, int]] = {}
        if ids:
            for row in session.scalars(
                select(ContentReaction).where(ContentReaction.content_id.in_(ids))
            ).all():
                liked, favorited = reactions.get(row.content_id, (0, 0))
                reactions[row.content_id] = (liked + (1 if row.liked else 0), favorited + (1 if row.favorited else 0))
        for content, channel in pairs:
            score = _heat(content, *reactions.get(content.id, (0, 0)))
            prev = best.get(content.id)
            if prev is None or score > prev[0]:
                best[content.id] = (score, content, channel)
        scored = sorted(
            best.values(),
            key=lambda item: (item[0], _dt_key(item[1].published_at) or _dt_key(item[1].created_at)),
            reverse=True,
        )
        return [_rail_card(session, content, channel) for _score, content, channel in scored[:limit]]

    return {
        "news": news,
        "today": ranked(today_cutoff, 5),
        "week": ranked(week_cutoff, 5),
    }
