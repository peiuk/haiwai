from collections import Counter
from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import exists, or_, select
from sqlalchemy.orm import Session

from app.api.v1.auth import optional_user
from app.core.db import get_db
from app.core.regions import open_regions
from app.feed import author_names, embed_card, home_channels, image_keys_of, reaction_flags
from app.keywords import load_keywords
from app.privacy import viewable
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
    # 私密房间的内容在 SQL 里排除，只取关键词这一列：原来每条内容再查一次库，右栏每次加载都要跑几百上千次查询。
    in_private_room = exists(
        select(ChannelItem.content_id)
        .join(Channel, Channel.id == ChannelItem.channel_id)
        .where(ChannelItem.content_id == Content.id, Channel.kind == "room", Channel.is_private.is_(True))
    )
    rows = session.scalars(
        select(Content.keywords_json).where(
            Content.status == "published",
            Content.deleted_at.is_(None),
            Content.published_at >= cutoff,
            ~in_private_room,
        )
    ).all()
    counter: Counter[str] = Counter()
    for raw in rows:
        for word in load_keywords(raw):
            counter[word] += 1
    keywords = [{"keyword": word, "count": count} for word, count in counter.most_common(bounded)]
    return {"keywords": keywords, "window_days": 30, "generated": utcnow().isoformat()}


@router.get("/search")
def search(
    q: str = "",
    session: Session = Depends(get_db),
    viewer: User | None = Depends(optional_user),
) -> dict[str, list[dict[str, object]]]:
    raw = q.strip()
    if not raw:
        return {"channels": [], "contents": [], "users": []}
    people = raw.startswith("@")
    topic = raw.startswith("#")
    needle = raw[1:].strip() if raw[0] in "#@" else raw
    if not needle:
        return {"channels": [], "contents": [], "users": []}
    # 用户输入的 % 和 _ 按字面匹配，不当通配符（否则搜「%」会匹配全部内容并整表扫描）。
    literal = needle.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    # 匹配一律用 ilike：PostgreSQL 的 like 区分大小写，搜 london 会找不到话题写成 London 的帖子
    pattern = f"%{literal}%"
    handle_pattern = f"%{literal.lower()}%"
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
            Channel.region_code.in_(list(open_regions(session))),  # 后台关闭的国家，频道搜不到
            or_(Channel.kind != "room", has_published),
            or_(Channel.name_hans.ilike(pattern, escape="\\"), Channel.name_hant.ilike(pattern, escape="\\"), Channel.code.ilike(pattern, escape="\\")),
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
            # 私密房间的帖子在 SQL 里排除（搜索对谁都不露私密内容）：先取 20 条再过滤，会被私密帖占满而搜不到公开帖
            viewable(None),
            or_(
                Content.title.ilike(pattern, escape="\\"),
                Content.summary.ilike(pattern, escape="\\"),
                Content.keywords_json.ilike(pattern, escape="\\"),
                Content.city_topic.ilike(pattern, escape="\\"),
                User.handle.ilike(handle_pattern, escape="\\"),
            ),
        )
        .order_by(Content.published_at.desc())
        .limit(20)
    ).all()
    results: list[dict[str, object]] = []
    # 结果页直接用信息流卡片展示，带上当前用户的点赞 / 收藏状态
    flags = reaction_flags(session, viewer.id if viewer else None, [row.id for row in contents])
    # 频道和作者整批查：原来每条结果各查三次库
    placed_in = home_channels(session, [row.id for row in contents])
    authors = author_names(session, [row.author_id for row in contents])
    for row in contents:
        liked, favorited = flags.get(row.id, (False, False))
        channel = placed_in.get(row.id)
        author_name, author_handle, author_avatar = authors.get(row.author_id or "", ("", "", ""))
        results.append(
            {
                "content_id": row.id,
                "title": row.title,
                "summary": row.summary,
                "type": row.type,
                "source_name": row.source_name or "",
                "licence_ref": row.licence_ref or "",
                "canonical_url": row.canonical_url,
                "author_id": row.author_id,
                "author_name": author_name,
                "author_handle": author_handle,
                "author_avatar": author_avatar,
                "channel_id": channel.id if channel else None,
                "channel_name": channel.name_hans if channel else "",
                "keywords": load_keywords(row.keywords_json),
                "image_keys": image_keys_of(row),
                "video_key": row.video_key,
                "embed": embed_card(row),
                "published_at": row.published_at.isoformat() if row.published_at else None,
                "liked": liked,
                "favorited": favorited,
            }
        )
    users: list[dict[str, object]] = []
    # 「#话题」只搜内容；「@」只按用户名；普通词同时匹配用户名和昵称
    if not topic:
        name_match = (
            User.handle.ilike(handle_pattern, escape="\\")
            if people
            else or_(User.handle.ilike(handle_pattern, escape="\\"), User.display_name.ilike(pattern, escape="\\"))
        )
        matches = session.scalars(
            select(User)
            .where(
                User.deleted_at.is_(None),
                User.status == "active",
                name_match,
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
                "avatar_key": row.avatar_key or "",
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
