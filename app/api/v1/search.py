from collections import Counter
from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import exists, or_, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.keywords import load_keywords
from app.privacy import can_view_content, is_private_room_content
from app.models import Channel, ChannelItem, Content, User, utcnow

router = APIRouter()


@router.get("/search/trending-keywords")
def trending_keywords(limit: int = 5, session: Session = Depends(get_db)) -> dict[str, object]:
    """热门关键词：统计近期已发布内容的关键词词频（近 30 天，取 Top N）。

    无真实趋势算法（时间窗口/地区权重待产品定义），当前用内容关键词频次做轻量聚合，
    对齐右栏「热门关键词」区块；点击后走 /search 检索。
    """
    bounded = min(max(limit, 1), 20)
    cutoff = utcnow() - timedelta(days=30)
    rows = session.scalars(
        select(Content)
        .where(Content.status == "published", Content.deleted_at.is_(None), Content.published_at >= cutoff)
    ).all()
    counter: Counter[str] = Counter()
    for content in rows:
        if is_private_room_content(session, content):
            continue
        for word in load_keywords(content.keywords_json):
            counter[word] += 1
    keywords = [{"keyword": word, "count": count} for word, count in counter.most_common(bounded)]
    return {"keywords": keywords, "window_days": 30, "generated": utcnow().isoformat()}


@router.get("/search")
def search(q: str = "", session: Session = Depends(get_db)) -> dict[str, list[dict[str, object]]]:
    raw = q.strip()
    if not raw:
        return {"channels": [], "contents": [], "users": []}
    people = raw.startswith("@")
    needle = raw[1:].strip() if raw[0] in "#@" else raw
    if not needle:
        return {"channels": [], "contents": [], "users": []}
    pattern = f"%{needle}%"
    handle_pattern = f"%{needle.lower()}%"
    has_published = exists(
        select(ChannelItem.channel_id)
        .join(Content, Content.id == ChannelItem.content_id)
        .where(
            ChannelItem.channel_id == Channel.id,
            Content.status == "published",
            Content.deleted_at.is_(None),
        )
    )
    channels = session.scalars(
        select(Channel)
        .where(
            Channel.is_active.is_(True),
            Channel.visibility == "public",
            Channel.is_private.is_(False),
            or_(Channel.kind != "room", has_published),
            or_(Channel.name_hans.like(pattern), Channel.name_hant.like(pattern), Channel.code.like(pattern)),
        )
        .order_by(Channel.code)
        .limit(20)
    ).all()
    contents = session.scalars(
        select(Content)
        .outerjoin(User, User.id == Content.author_id)
        .where(
            Content.status == "published",
            Content.deleted_at.is_(None),
            or_(
                Content.title.like(pattern),
                Content.summary.like(pattern),
                Content.keywords_json.like(pattern),
                Content.city_topic.like(pattern),
                User.handle.like(handle_pattern),
            ),
        )
        .order_by(Content.published_at.desc())
        .limit(20)
    ).all()
    results: list[dict[str, object]] = []
    for row in contents:
        if not can_view_content(session, row, None):
            continue
        placed = session.scalar(
            select(ChannelItem).where(ChannelItem.content_id == row.id, ChannelItem.origin_room_id.is_(None))
        )
        channel = session.get(Channel, placed.channel_id) if placed is not None else None
        author = session.get(User, row.author_id) if row.author_id else None
        results.append(
            {
                "content_id": row.id,
                "title": row.title,
                "summary": row.summary,
                "type": row.type,
                "source_name": row.source_name or "",
                "licence_ref": row.licence_ref or "",
                "canonical_url": row.canonical_url,
                "author_name": author.display_name if author else "",
                "author_handle": author.handle or "" if author else "",
                "channel_id": channel.id if channel else None,
                "channel_name": channel.name_hans if channel else "",
            }
        )
    users: list[dict[str, object]] = []
    if people:
        matches = session.scalars(
            select(User)
            .where(
                User.deleted_at.is_(None),
                User.status == "active",
                User.handle.like(handle_pattern),
            )
            .order_by(User.handle)
            .limit(20)
        ).all()
        users = [
            {
                "user_id": row.id,
                "display_name": row.display_name,
                "handle": row.handle or "",
                "avatar_tone": row.avatar_tone,
                "city_label": row.city_label or "",
            }
            for row in matches
        ]
    return {
        "users": users,
        "channels": [
            {"id": row.id, "code": row.code, "name_hans": row.name_hans, "kind": row.kind, "room_type": row.room_type}
            for row in channels
        ],
        "contents": results,
    }
