import json
from datetime import timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel, field_validator, model_validator
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.embed import embed_fields
from app.api.v1.auth import current_user, optional_user, require_verified_phone
from app.api.v1.uploads import owned_upload
from app.api.v1.me import active_channel
from app.api.v1.room_social import apply_comment_like, comment_like_state, mention_count, mention_users, publish_comment
from app.core.audit import write_audit
from app.guard import blocked_term_in, first_status, hide_if_widely_reported, review_on
from app.core.db import get_db
from app.core.errors import APIError
from app.keywords import clean_city_topic, collect_keywords, dump_keywords, load_keywords, resolve_keywords, suggest_keywords
from app.privacy import can_view_content, is_private_room_content
from app.reports import ReportBody, report_receipt
from app.recommend import country_blocked, is_roaming
from app.rooms import drop_pushes, notify_room_update
from app.feed import MAX_LISTING_IMAGES, image_keys_of
from app.models import (
    Channel,
    ChannelCollaborator,
    ChannelItem,
    ChannelSubscription,
    Content,
    ContentReaction,
    ModerationCase,
    Notification,
    RoomComment,
    User,
    utcnow,
)

router = APIRouter()
HOURLY_POST_LIMIT = 5
REVIEW_LIMIT = 3


class PostBody(BaseModel):
    channel_id: str | None = None
    title: str
    body: str
    # image_key 兼容旧客户端单图；新客户端用 image_keys（最多 4 张）。
    image_key: str | None = None
    image_keys: list[str] = []
    video_key: str | None = None
    video_url: str | None = None  # 视频外链（YouTube / 哔哩哔哩），和上传视频二选一
    post_type: str = "text"
    rights_confirmed: bool = False
    keywords: list[str] = []
    city_topic: str | None = None
    keyword_source: str | None = None

    @field_validator("image_keys")
    @classmethod
    def bounded_images(cls, value: list[str]) -> list[str]:
        keys = [key for key in dict.fromkeys(value) if key]
        if len(keys) > MAX_LISTING_IMAGES:
            raise ValueError(f"最多上传 {MAX_LISTING_IMAGES} 张图片")
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
        # 保留 None（未传）与 ""（用户显式删除城市话题）的语义区分，交给 create_post 判断。
        if value is None:
            return None
        if value == "":
            return ""
        return clean_city_topic(value)

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

    @field_validator("post_type")
    @classmethod
    def known_post_type(cls, value: str) -> str:
        if value not in {"text", "video", "topic"}:
            raise ValueError("内容类型不正确")
        return value


def _check_hourly_limit(session: Session, user_id: str) -> None:
    # 只数最近一小时的条数：原来把作者全部帖子的时间都读出来再在 Python 里过滤，帖子越多越慢。
    cutoff = utcnow() - timedelta(hours=1)
    count = session.scalar(
        select(func.count()).select_from(Content).where(Content.author_id == user_id, Content.created_at >= cutoff)
    )
    if (count or 0) >= HOURLY_POST_LIMIT:
        raise APIError(429, "RATE_LIMITED", "每小时最多发布 5 条")


@router.post("/contents")
def create_post(
    body: PostBody,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    require_verified_phone(user, "发布")
    if is_roaming(session, user):
        raise APIError(403, "ROAMING_READONLY", "跨国漫游下仅供浏览，发帖请切换至本地")
    channel = None
    if body.channel_id:
        channel = session.get(Channel, body.channel_id)
        owns_pending = (
            channel is not None
            and channel.kind == "room"
            and channel.visibility == "public"
            and not channel.is_active
            and (
                channel.owner_id == user.id
                or session.get(ChannelCollaborator, (channel.id, user.id)) is not None
            )
        )
        if not owns_pending:
            channel = active_channel(session, body.channel_id)
        if country_blocked(session, user, channel):
            raise APIError(403, "REGION_BLOCKED", "当前国家看不到这个频道")
        if channel.kind == "room" and channel.is_private and channel.owner_id != user.id and session.get(ChannelSubscription, (user.id, channel.id)) is None:
            raise APIError(403, "ROOM_PRIVATE", "加入私密房间后才能发布")
    # 归一化图片列表：新客户端 image_keys 优先，兼容旧客户端单图 image_key。
    keys = list(body.image_keys)
    if not keys and body.image_key:
        keys = [body.image_key]
    for key in keys:
        owned_upload(session, user, key)
    video_url = (body.video_url or "").strip()
    if video_url and body.post_type == "video":
        raise APIError(400, "VALIDATION_FAILED", "上传视频和视频外链只能选一个")
    embed = embed_fields(video_url) if video_url else {}
    _check_hourly_limit(session, user.id)
    prior = session.scalar(
        select(func.count()).select_from(Content).where(Content.author_id == user.id, Content.deleted_at.is_(None))
    )
    now = utcnow()
    # 后台关了帖子审核时，新用户的前几条也直接发布；敏感词照样拦
    status = "pending" if review_on(session, "post") and (prior or 0) < REVIEW_LIMIT else "published"
    if status == "published" and blocked_term_in(session, body.title, body.body):
        status = "pending"  # 命中敏感词 / 链接黑名单：不直接发布，先给管理员看
    if body.post_type == "video":
        if not body.rights_confirmed:
            raise APIError(400, "RIGHTS_REQUIRED", "发布视频前需要确认是原创且有权使用")
        if not body.video_key:
            raise APIError(400, "VALIDATION_FAILED", "发视频需要先上传一段视频")
        uploaded = owned_upload(session, user, body.video_key)
        if not uploaded.content_type.startswith("video/"):
            raise APIError(400, "VALIDATION_FAILED", "发视频需要先上传一段视频")
        stored_type = "video"
    elif body.post_type == "topic" and not collect_keywords(body.keywords, body.body):
        raise APIError(400, "TOPIC_REQUIRED", "发话题至少要有一个话题")
    else:
        stored_type = "post"
    if embed:
        stored_type = "embed"  # 外链视频按外链规则：不进推荐和发现
    # 城市话题：官方默认自动用用户注册时填的城市名，作为发帖默认带上的话题之一。
    # body.city_topic 为 None → 未显式指定，回落到 user.city_label；
    # body.city_topic 为 "" → 用户主动删除了城市话题，尊重用户，不自动加。
    if body.city_topic is None:
        city = clean_city_topic(user.city_label)
    else:
        city = clean_city_topic(body.city_topic)
    words, source = resolve_keywords(body.keywords, body.title, body.body, body.keyword_source)
    content = Content(
        type=stored_type,
        status=status,
        author_id=user.id,
        title=body.title,
        summary=body.body[:500],
        body=body.body,
        keywords_json=dump_keywords(words),
        keyword_source=source,
        city_topic=city,
        source_name=user.display_name,
        image_key=keys[0] if keys else None,
        image_keys_json=json.dumps(keys),
        video_key=body.video_key if body.post_type == "video" else None,
        rights_confirmed=body.rights_confirmed if body.post_type == "video" else False,
        published_at=now if status == "published" else None,
        **embed,
    )
    session.add(content)
    session.flush()
    if channel is not None:
        session.add(ChannelItem(channel_id=channel.id, content_id=content.id, added_at=now))
        if status == "published" and channel.kind == "room" and not channel.is_active and channel.review_status == "pending":
            channel.is_active = True
            channel.review_status = "approved"
        if status == "published":
            notify_room_update(session, channel, content)
    session.commit()
    return {
        "content_id": content.id,
        "status": content.status,
        "type": content.type,
        "keywords": words,
        "keyword_source": source,
        "city_topic": content.city_topic or "",
    }


@router.delete("/contents/{content_id}")
def delete_content(
    content_id: str,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    content = session.get(Content, content_id)
    if content is None or content.deleted_at is not None:
        raise APIError(404, "CONTENT_NOT_FOUND", "内容不存在")
    if content.author_id != user.id:
        raise APIError(403, "FORBIDDEN", "只能删除自己的内容")
    content.status = "deleted"
    content.deleted_at = utcnow()
    drop_pushes(session, content.id)
    write_audit(session, user.id, "content.delete", "content", content.id)
    session.commit()
    return {"content_id": content.id, "status": "deleted"}


@router.get("/contents/{content_id}")
def get_content(
    content_id: str,
    user: User | None = Depends(optional_user),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    content = session.get(Content, content_id)
    if content is None or content.deleted_at is not None:
        raise APIError(404, "CONTENT_NOT_FOUND", "内容不存在")
    if content.status != "published" and (user is None or content.author_id != user.id):
        raise APIError(404, "CONTENT_NOT_FOUND", "内容不存在")
    if not can_view_content(session, content, user):
        raise APIError(404, "CONTENT_NOT_FOUND", "内容不存在")
    # 浏览埋点：详情页每次打开自增一次浏览计数，供「本周看得最多」排行使用。
    # 在数据库里原地加一并提交：原来改了内存对象却没提交，计数从没保存过；同时打开也不会少算。
    session.execute(update(Content).where(Content.id == content.id).values(view_count=func.coalesce(Content.view_count, 0) + 1))
    session.commit()
    author = session.get(User, content.author_id) if content.author_id else None
    liked = False
    favorited = False
    if user is not None:
        reaction = session.get(ContentReaction, (user.id, content.id))
        if reaction is not None:
            liked = reaction.liked
            favorited = reaction.favorited
    placed = session.scalar(
        select(ChannelItem).where(ChannelItem.content_id == content.id, ChannelItem.origin_room_id.is_(None))
    )
    channel = session.get(Channel, placed.channel_id) if placed is not None else None
    category = None
    if channel is not None and channel.kind == "room" and channel.parent_channel_id:
        parent = session.get(Channel, channel.parent_channel_id)
        category = parent.category if parent is not None else channel.category
    elif channel is not None:
        category = channel.category
    joined = user is not None and channel is not None and session.get(ChannelSubscription, (user.id, channel.id)) is not None
    repost_of = None
    if content.repost_of_id:
        original = session.get(Content, content.repost_of_id)
        if original is not None:
            repost_of = {"content_id": original.id, "title": original.title}
    return {
        "content_id": content.id,
        "title": content.title,
        "title_hant": content.title_hant or content.title,
        "summary": content.summary,
        "body": content.body,
        "keywords": load_keywords(content.keywords_json),
        "city_topic": content.city_topic or "",
        "keyword_source": content.keyword_source or "",
        "source_name": content.source_name or "",
        "licence_ref": content.licence_ref or "",
        "canonical_url": content.canonical_url,
        "image_key": content.image_key,
        "image_keys": image_keys_of(content),
        "video_key": content.video_key,
        "published_at": content.published_at.isoformat() if content.published_at else None,
        "rights_confirmed": content.rights_confirmed,
        "type": content.type,
        "embed_status": content.embed_status,
        "embed_provider_code": content.embed_provider_code,
        "author_id": content.author_id,
        "author_name": author.display_name if author else None,
        "author_handle": author.handle or "" if author else "",
        "author_avatar": author.avatar_key or "" if author else "",
        "channel_id": channel.id if channel else None,
        "channel_name": channel.name_hans if channel else "",
        "category": category,
        "is_joined": joined,
        "repost_of": repost_of,
        "status": content.status,
        "liked": liked,
        "favorited": favorited,
    }


@router.post("/contents/{content_id}/report")
def report_content(
    content_id: str,
    body: ReportBody,
    user: User | None = Depends(optional_user),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    content = session.get(Content, content_id)
    if content is None or content.deleted_at is not None or content.status != "published" or not can_view_content(session, content, user):
        raise APIError(404, "CONTENT_NOT_FOUND", "内容不存在")
    if user is not None and content.author_id == user.id:
        raise APIError(403, "SELF_REPORT", "不能举报自己的内容")
    if user is not None:
        existing = session.scalar(
            select(ModerationCase.id).where(
                ModerationCase.content_id == content.id,
                ModerationCase.reporter_id == user.id,
            )
        )
        if existing:
            raise APIError(409, "DUPLICATE_REPORT", "你已经举报过这条内容")
    else:
        # 游客没法按人去重：同一条内容已有待处理的游客举报就直接复用，脚本刷不爆审核队列。
        pending = session.scalar(
            select(ModerationCase).where(
                ModerationCase.content_id == content.id,
                ModerationCase.reporter_id.is_(None),
                ModerationCase.status == "open",
            )
        )
        if pending is not None:
            return report_receipt(pending)
    case = ModerationCase(
        content_id=content.id,
        reporter_id=user.id if user else None,
        reason=body.reason,
        detail=body.detail,
    )
    session.add(case)
    session.flush()
    write_audit(session, user.id if user else None, "content.report", "content", content.id)
    hide_if_widely_reported(session, content)
    session.commit()
    return report_receipt(case)


class KeywordBody(BaseModel):
    title: str = ""
    body: str = ""
    category: str | None = None


@router.post("/ai/keywords")
def keywords(body: KeywordBody, _user: User = Depends(current_user)) -> dict[str, object]:
    words = suggest_keywords(body.title, body.body, body.category)
    return {"keywords": words, "source": "ai_auto", "max": 5}


def _reaction(session: Session, user_id: str, content_id: str) -> ContentReaction:
    row = session.get(ContentReaction, (user_id, content_id))
    if row is None:
        row = ContentReaction(user_id=user_id, content_id=content_id)
        session.add(row)
    return row


def _toggle(session: Session, user: User, content_id: str, field: str) -> dict[str, bool]:
    content = session.get(Content, content_id)
    if content is None or content.deleted_at is not None or content.status != "published" or not can_view_content(session, content, user):
        raise APIError(404, "CONTENT_NOT_FOUND", "内容不存在")
    row = _reaction(session, user.id, content.id)
    current = bool(getattr(row, field))
    setattr(row, field, not current)
    session.commit()
    return {field: not current}


class RepostBody(BaseModel):
    channel_id: str
    body: str = ""

    @field_validator("body")
    @classmethod
    def repost_note(cls, value: str) -> str:
        text = value.strip()
        if len(text) > 500:
            raise ValueError("转发附言最多 500 个字")
        return text


class ReplyBody(BaseModel):
    body: str
    parent_id: str | None = None
    image_key: str | None = None

    @field_validator("body")
    @classmethod
    def reply_length(cls, value: str) -> str:
        if len(value) > 1000:
            raise ValueError("回复需要 1 到 1000 个字")
        return value

    @model_validator(mode="after")
    def require_text_or_image(self) -> "ReplyBody":
        if not self.body.strip() and not self.image_key:
            raise ValueError("回复需要文字或一张图片")
        return self


def _visible_content(session: Session, content_id: str, user: User | None) -> Content:
    content = session.get(Content, content_id)
    if content is None or content.deleted_at is not None or content.status != "published" or not can_view_content(session, content, user):
        raise APIError(404, "CONTENT_NOT_FOUND", "内容不存在")
    return content


@router.get("/contents/{content_id}/comments")
def list_replies(
    content_id: str,
    user: User | None = Depends(optional_user),
    session: Session = Depends(get_db),
) -> dict[str, list[dict[str, object]]]:
    content = _visible_content(session, content_id, user)
    rows = session.scalars(
        select(RoomComment)
        .where(
            RoomComment.content_id == content.id,
            RoomComment.removed_at.is_(None),
            (RoomComment.status == "published")
            | ((RoomComment.status == "pending") & (RoomComment.author_id == (user.id if user else ""))),
        )
        .order_by(RoomComment.created_at)
    ).all()
    items: list[dict[str, object]] = []
    counts, liked = comment_like_state(session, user, [row.id for row in rows])
    for row in rows:
        author = session.get(User, row.author_id)
        items.append(
            {
                "id": row.id,
                "author_id": row.author_id,
                "author_name": author.display_name if author else "",
                "author_handle": author.handle or "" if author else "",
                "author_avatar": author.avatar_key or "" if author else "",
                "mentions": [person.handle or "" for person in mention_users(session, row.body)],
                "like_count": counts.get(row.id, 0),
                "liked": row.id in liked,
                "body": row.body,
                "image_key": row.image_key,
                "parent_id": row.parent_id,
                "status": row.status,
                "created_at": row.created_at.isoformat(),
            }
        )
    return {"items": items}


@router.post("/contents/{content_id}/comments")
def create_reply(
    content_id: str,
    body: ReplyBody,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    content = _visible_content(session, content_id, user)
    item = session.scalars(select(ChannelItem).where(ChannelItem.content_id == content.id)).first()
    if item is None:
        raise APIError(404, "CONTENT_NOT_FOUND", "内容不存在")
    if body.parent_id:
        parent = session.get(RoomComment, body.parent_id)
        if parent is None or parent.content_id != content.id or parent.removed_at is not None:
            raise APIError(404, "COMMENT_NOT_FOUND", "要回复的留言不存在")
    if body.image_key:
        owned_upload(session, user, body.image_key)
    now = utcnow()
    recent = session.scalar(
        select(func.count())
        .select_from(RoomComment)
        .where(
            RoomComment.content_id == content.id,
            RoomComment.author_id == user.id,
            RoomComment.created_at >= now - timedelta(minutes=1),
        )
    )
    if (recent or 0) >= 5:
        raise APIError(429, "RATE_LIMITED", "回复太频繁")
    comment = RoomComment(
        room_id=item.channel_id,
        content_id=content.id,
        parent_id=body.parent_id,
        author_id=user.id,
        body=body.body,
        image_key=body.image_key,
        mention_count=mention_count(body.body),
    )
    session.add(comment)
    session.flush()
    if first_status(session, "comment", body.body) == "published":
        publish_comment(session, comment)
    if content.author_id and content.author_id != user.id:
        session.add(
            Notification(
                user_id=content.author_id,
                kind="reply",
                body=f"{user.display_name} 回复了「{content.title}」"[:200],
                content_id=content.id,
            )
        )
    session.commit()
    return {"comment_id": comment.id, "status": comment.status}


@router.post("/contents/{content_id}/comments/{comment_id}/like")
def toggle_reply_like(
    content_id: str,
    comment_id: str,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    content = _visible_content(session, content_id, user)
    comment = session.get(RoomComment, comment_id)
    if comment is None or comment.content_id != content.id or comment.removed_at is not None or comment.status != "published":
        raise APIError(404, "COMMENT_NOT_FOUND", "留言不存在")
    return apply_comment_like(session, user, comment)


@router.delete("/contents/{content_id}/comments/{comment_id}")
def remove_reply(
    content_id: str,
    comment_id: str,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    content = session.get(Content, content_id)
    comment = session.get(RoomComment, comment_id)
    if content is None or comment is None or comment.content_id != content.id or comment.removed_at is not None:
        raise APIError(404, "COMMENT_NOT_FOUND", "留言不存在")
    if comment.author_id != user.id and content.author_id != user.id:
        raise APIError(403, "FORBIDDEN", "不能处理这条留言")
    comment.status = "removed"
    comment.removed_at = utcnow()
    session.commit()
    return {"comment_id": comment.id, "status": comment.status}


@router.post("/contents/{content_id}/repost")
def repost_content(
    content_id: str,
    body: RepostBody,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    require_verified_phone(user, "转发")
    original = _visible_content(session, content_id, user)
    if is_private_room_content(session, original):
        raise APIError(403, "ROOM_PRIVATE", "私密房间内容不能转发")
    if original.type == "repost":
        raise APIError(400, "VALIDATION_FAILED", "不能转发一条转发")
    channel = active_channel(session, body.channel_id)
    if channel.kind == "room" and channel.is_private and channel.owner_id != user.id and session.get(ChannelSubscription, (user.id, channel.id)) is None:
        raise APIError(403, "ROOM_PRIVATE", "加入私密房间后才能发布")
    existing = session.scalar(
        select(Content).where(
            Content.author_id == user.id,
            Content.repost_of_id == original.id,
            Content.deleted_at.is_(None),
        )
    )
    if existing is not None:
        return {"content_id": existing.id, "status": existing.status}
    _check_hourly_limit(session, user.id)
    now = utcnow()
    note = body.body or original.summary or ""
    content = Content(
        type="repost",
        status="published",
        author_id=user.id,
        repost_of_id=original.id,
        title=original.title,
        summary=note[:500],
        body=note,
        source_name=original.source_name,
        licence_ref=original.licence_ref,
        canonical_url=original.canonical_url,
        published_at=now,
    )
    session.add(content)
    session.flush()
    session.add(ChannelItem(channel_id=channel.id, content_id=content.id, added_at=now))
    session.commit()
    return {"content_id": content.id, "status": content.status}


@router.post("/contents/{content_id}/like")
def toggle_like(
    content_id: str,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, bool]:
    return _toggle(session, user, content_id, "liked")


@router.post("/contents/{content_id}/favorite")
def toggle_favorite(
    content_id: str,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, bool]:
    return _toggle(session, user, content_id, "favorited")
