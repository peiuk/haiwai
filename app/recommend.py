from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.feed import author_names, card_extras, content_titles, reaction_flags, repost_context
from app.core.regions import is_open_region
from app.models import Channel, ChannelItem, ChannelSubscription, Content, User, UserRegionPref

CANDIDATES = 500

_REASONS = {
    "cooccur": "和你加入的频道常一起出现",
    "region": "和你当前的国家一致",
    "activity": "这个频道最近有更新",
    "curated": "来自官方精选频道",
    "featured": "编辑精选",
}


def effective_region(session: Session, user: User | None) -> str:
    if user is None:
        return "GLOBAL"
    pref = session.get(UserRegionPref, user.id)
    if pref is None:
        return "GLOBAL"
    if pref.browse_region_code:
        return pref.browse_region_code
    code = pref.region_code or "GLOBAL"
    # 归属国家未开通 -> 回落到国际频道（GLOBAL），避免空白页。
    return code if is_open_region(session, code) else "GLOBAL"


def is_roaming(session: Session, user: User | None) -> bool:
    if user is None:
        return False
    pref = session.get(UserRegionPref, user.id)
    if pref is None or not pref.browse_region_code:
        return False
    home = (pref.region_code or "GLOBAL").upper()
    browse = pref.browse_region_code.upper()
    return home not in {"UK", "GLOBAL"} and browse in {"UK", "GLOBAL"}


def country_blocked(session: Session, user: User | None, channel) -> bool:
    if user is None or channel.region_code in {"", "GLOBAL"}:
        return False
    if session.get(UserRegionPref, user.id) is None:
        return False
    return effective_region(session, user) != channel.region_code


def _cooccurrence(session: Session, subscribed: set[str]) -> dict[str, float]:
    if not subscribed:
        return {}
    peer_ids = set(
        session.scalars(select(ChannelSubscription.user_id).where(ChannelSubscription.channel_id.in_(subscribed))).all()
    )
    if not peer_ids:
        return {}
    counts: dict[str, set[str]] = {}
    pairs = session.execute(
        select(ChannelSubscription.user_id, ChannelSubscription.channel_id).where(ChannelSubscription.user_id.in_(peer_ids))
    ).all()
    for user_id, channel_id in pairs:
        if channel_id in subscribed:
            continue
        counts.setdefault(channel_id, set()).add(user_id)
    largest = max((len(users) for users in counts.values()), default=0)
    if largest == 0:
        return {}
    return {channel_id: len(users) / largest for channel_id, users in counts.items()}


def for_you(session: Session, user: User | None, limit: int | None = 12, order: str = "ranked") -> list[dict[str, object]]:
    """user 为 None 时是游客版：没有加入的频道、不看个人数据，只按新鲜度 / 活跃度 / 官方精选排序。"""
    region = effective_region(session, user)
    user_id = user.id if user else None
    subscribed = set(
        session.scalars(select(ChannelSubscription.channel_id).where(ChannelSubscription.user_id == user_id)).all()
    ) if user_id else set()
    together = _cooccurrence(session, subscribed)
    private_room_content = (
        select(ChannelItem.content_id)
        .join(Channel, Channel.id == ChannelItem.channel_id)
        .where(Channel.kind == "room", Channel.is_private.is_(True))
    )
    regions = ("GLOBAL",) if region == "GLOBAL" else (region, "GLOBAL")
    # 游客也能调用，所以过滤和取数都在数据库里做，每次只取最新的一批来打分。
    # shortcut: 只看最新 500 条收录（72 小时后新鲜度已降到底），内容量大到这批不够分时再改成按天窗口 + 索引。
    rows = session.scalars(
        select(ChannelItem)
        .join(Content, Content.id == ChannelItem.content_id)
        .join(Channel, Channel.id == ChannelItem.channel_id)
        .where(
            Content.status == "published",
            Content.deleted_at.is_(None),
            Content.type.not_in(("listing", "embed", "repost")),
            ChannelItem.origin_room_id.is_(None),
            Channel.kind != "room",
            Channel.is_active.is_(True),
            Channel.region_code.in_(regions),
            ChannelItem.content_id.not_in(private_room_content),
        )
        .order_by(ChannelItem.added_at.desc())
        .limit(CANDIDATES)
        .options(joinedload(ChannelItem.channel), joinedload(ChannelItem.content))
    ).unique().all()
    now = datetime.now(timezone.utc)
    recent: dict[str, int] = {}
    for item in rows:
        added = item.added_at if item.added_at.tzinfo else item.added_at.replace(tzinfo=timezone.utc)
        if (now - added).total_seconds() <= 7 * 24 * 3600:
            recent[item.channel_id] = recent.get(item.channel_id, 0) + 1
    authors = author_names(session, [item.content.author_id for item in rows])
    flags = reaction_flags(session, user_id, [item.content_id for item in rows])
    repost_titles, reposted_ids = repost_context(session, user_id, [item.content for item in rows])
    best: dict[str, tuple[float, dict[str, object]]] = {}
    for item in rows:
        channel = item.channel
        added = item.added_at if item.added_at.tzinfo else item.added_at.replace(tzinfo=timezone.utc)
        age_hours = max((now - added).total_seconds() / 3600, 0)
        freshness = max(0.05, 1 - age_hours / 72)
        region_match = 1.0 if channel.region_code == region else 0.0
        activity = min(recent.get(channel.id, 0), 5) / 5
        curated = 1.0 if channel.kind == "official_curated" else 0.0
        cooccur = together.get(channel.id, 0.0)
        featured = item.content.featured_at is not None
        if featured:
            freshness = max(freshness, 0.5)  # 精选内容不随时间很快沉底
        parts = {
            "cooccur": 0.40 * cooccur,
            "region": 0.30 * region_match,
            "activity": 0.20 * activity,
            "curated": 0.10 * curated,
            "featured": 0.50 if featured else 0.0,
        }
        reason_code = max(parts, key=parts.get)
        reason = _REASONS[reason_code]
        if user is None:
            # 游客没有「你的国家 / 你加入的频道」，理由只能说内容本身的情况。
            reason_code = "featured" if featured else "activity" if activity >= curated else "curated"
            reason = _REASONS[reason_code] if parts[reason_code] > 0 else "最近发布的公开内容"
        penalty = 0.88 if channel.id in subscribed else 1.0
        score = sum(parts.values()) * freshness * penalty
        title_hans, title_hant, summary_hans, summary_hant = content_titles(item.content)
        card = {
            "content_id": item.content_id,
            "title": title_hans,
            "title_hant": title_hant,
            "summary": summary_hans,
            "summary_hant": summary_hant,
            "source_name": item.content.source_name or "",
            "licence_ref": item.content.licence_ref or "",
            "canonical_url": item.content.canonical_url,
            "channels": [channel.code],
            "channel_id": channel.id,
            "channel_name": channel.name_hans,
            "is_joined": channel.id in subscribed,
            "reason_code": reason_code,
            "reason": reason,
            "featured": featured,
            "added_at": item.added_at.isoformat(),
            **card_extras(item.content, None, authors.get(item.content.author_id or "", ("", ""))),
            "liked": flags.get(item.content_id, (False, False))[0],
            "favorited": flags.get(item.content_id, (False, False))[1],
            "reposted": item.content_id in reposted_ids,
            "repost_of": (
                {"content_id": item.content.repost_of_id, "title": repost_titles.get(item.content.repost_of_id, "")}
                if item.content.repost_of_id
                else None
            ),
        }
        current = best.get(item.content_id)
        if current is None or score > current[0]:
            best[item.content_id] = (score, card)
    if order == "time":
        ranked = sorted(best.values(), key=lambda pair: str(pair[1]["added_at"]), reverse=True)
    else:
        ranked = sorted(best.values(), key=lambda pair: pair[0], reverse=True)
    pool = [card for _score, card in ranked]
    # limit=None 返回完整有序池，供 API 层做游标分页（首屏仍由 limit 控制）。
    return pool if limit is None else pool[:limit]
