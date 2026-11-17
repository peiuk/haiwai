import json
from datetime import timedelta

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, field_validator, model_validator
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.orm import Session

from app.embed import embed_fields
from app.api.v1.auth import current_user, optional_user, require_verified_phone
from app.api.v1.channels import TextBody  # 标题 + 正文的长度规则只留这一份
from app.api.v1.uploads import owned_upload
from app.api.v1.me import active_channel
from app.api.v1.room_social import (
    apply_comment_like,
    comment_like_state,
    mention_count,
    mention_handles,
    mentioned_handles,
    publish_comment,
)
from app.core.audit import write_audit
from app.guard import blocked_term_in, check_hourly_limit, first_status, hide_if_widely_reported, review_on
from app.core.db import get_db
from app.core.errors import APIError
from app.core.pagination import decode_cursor, encode_cursor, parse_added_at
from app.keywords import clean_city_topic, collect_keywords, dump_keywords, load_keywords, resolve_keywords
from app.privacy import can_view_content, is_private_room_content, is_room_editor, require_not_blocked_by
from app.reports import ReportBody, limit_reports, report_receipt
from app.recommend import country_blocked, is_roaming
from app.rooms import drop_pushes, notify_room_update, require_not_banned
from app.feed import author_names, MAX_LISTING_IMAGES, image_keys_of
from app.models import (
    Channel,
    ChannelCollaborator,
    ChannelItem,
    ChannelSubscription,
    Content,
    ContentReaction,
    ModerationCase,
    RoomComment,
    User,
    utcnow,
)

router = APIRouter()
REVIEW_LIMIT = 3
HOURLY_REPLY_LIMIT = 30  # 一个人一小时在全站帖子下最多回复这么多条
# 彩色背景：只能选这几个预设（颜色本身在前端 utils/postBg.ts，两边名字要一致）
BG_STYLES = {"red", "purple", "blue", "sunset", "pink", "green", "dark", "yellow"}
BG_MAX_LEN = 130  # 背景上字大，长了读不下去；和 Facebook 一样只给短文字用


def _known_bg(value: str | None) -> str | None:
    if not value:
        return None
    if value not in BG_STYLES:
        raise ValueError("背景颜色不正确")
    return value


def _require_bg_fits(bg_style: str | None, text: str, has_media: bool) -> None:
    """页面上会自动去掉背景，这里再拦一次：直接调接口也不能给长文或带图视频的帖子加背景。"""
    if bg_style and (has_media or len(text) > BG_MAX_LEN):
        raise APIError(400, "VALIDATION_FAILED", f"彩色背景只能用在 {BG_MAX_LEN} 字以内、不带图片和视频的文字帖")


class EditBody(TextBody):
    bg_style: str | None = None  # 编辑时带上当前的背景；不传就是去掉背景

    @field_validator("bg_style")
    @classmethod
    def known_bg(cls, value: str | None) -> str | None:
        return _known_bg(value)


class PostBody(TextBody):
    bg_style: str | None = None
    channel_id: str | None = None
    # image_key 兼容旧客户端单图；新客户端用 image_keys（最多 6 张）。
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

    @field_validator("bg_style")
    @classmethod
    def known_bg(cls, value: str | None) -> str | None:
        return _known_bg(value)

    @field_validator("post_type")
    @classmethod
    def known_post_type(cls, value: str) -> str:
        if value not in {"text", "video", "topic"}:
            raise ValueError("内容类型不正确")
        return value


def _approved_posts(session: Session, user_id: str) -> int:
    """新用户前 REVIEW_LIMIT 条要审：只数审核通过的。连待审的也数的话，发 3 条垃圾帖等着，第 4 条就直接公开了。"""
    return int(
        session.scalar(
            select(func.count())
            .select_from(Content)
            .where(Content.author_id == user_id, Content.deleted_at.is_(None), Content.status == "published")
        )
        or 0
    )


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
            and channel.review_status == "pending"  # 被拒、被下架的房间不算：房主不能接着往里发、再通知原来的成员
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
        require_not_banned(session, [channel.id], user.id)
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
    _require_bg_fits(body.bg_style, body.body, bool(keys or video_url or body.video_key or body.post_type == "video"))
    check_hourly_limit(session, user.id)
    prior = _approved_posts(session, user.id)
    now = utcnow()
    # 后台关了帖子审核时，新用户的前几条也直接发布；敏感词照样拦。
    # 已上线房间里的帖子由房主管（能删），不进后台审核；还没上线的房间仍要等第一条通过才上线。
    in_live_room = channel is not None and channel.kind == "room" and channel.is_active
    # 房间里只有房主 / 协作者能直接发；其他人发的算投稿，等房主通过（channels.decide_submission）。
    # 页面上本来就是这样分的，这里不拦的话直接调接口就能绕过房主。
    is_submission = in_live_room and not is_room_editor(session, channel, user)
    needs_admin = not in_live_room and review_on(session, "post", user) and (prior or 0) < REVIEW_LIMIT
    status = "pending" if is_submission or needs_admin else "published"
    if status == "published" and blocked_term_in(session, body.title, body.body):
        status = "pending"  # 命中敏感词 / 链接黑名单：不直接发布，先给管理员看
    if body.post_type == "video":
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
        bg_style=body.bg_style,
        rights_confirmed=body.post_type == "video",  # 不再单独勾选：上传即按用户协议视为本人原创
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
    own = content.author_id == user.id
    room = None if own else _home_room(session, content)
    if not own and (room is None or room.owner_id != user.id):
        raise APIError(403, "FORBIDDEN", "只能删除自己的内容，或自己房间里的帖子")
    from app.api.v1.admin import _delete_files, _release_uploads  # 放在函数里：admin 很重，只有这里用到

    content.status = "deleted"
    content.deleted_at = utcnow()
    drop_pushes(session, content.id)
    # 作者 / 房主删的帖子不能恢复：图片视频一并删掉（不删的话知道原链接的人还能打开）；别的帖子还在用的不动
    orphaned = _release_uploads(session, set(image_keys_of(content)) | {content.video_key}, content.id)
    write_audit(session, user.id, "content.delete" if own else "room.content.remove", "content", content.id)
    session.commit()
    _delete_files(orphaned)  # 提交成功后再删文件
    return {"content_id": content.id, "status": "deleted"}


def _home_room(session: Session, content: Content) -> Channel | None:
    """帖子发在哪个房间（转推到频道的那份不算）；不在房间里返回 None。"""
    placed = session.scalar(
        select(ChannelItem).where(ChannelItem.content_id == content.id, ChannelItem.origin_room_id.is_(None))
    )
    channel = session.get(Channel, placed.channel_id) if placed is not None else None
    return channel if channel is not None and channel.kind == "room" else None


EDITABLE_TYPES = ("post", "video", "embed")  # 分类信息有自己的字段，转发只是引用，都不走这里


@router.patch("/contents/{content_id}")
def edit_content(
    content_id: str,
    body: EditBody,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    content = session.get(Content, content_id)
    if content is None or content.deleted_at is not None:
        raise APIError(404, "CONTENT_NOT_FOUND", "内容不存在")
    # 只有作者能改：房主改别人的帖子会变成「替别人说话」，房主管不了的内容直接删
    if content.author_id != user.id:
        raise APIError(403, "FORBIDDEN", "只能编辑自己的内容")
    if content.type not in EDITABLE_TYPES or content.status not in ("published", "pending"):
        raise APIError(409, "NOT_EDITABLE", "这条内容不能编辑")
    room = _home_room(session, content)
    if room is not None:
        require_not_banned(session, [room.id], user.id)
    _require_bg_fits(body.bg_style, body.body, content.type != "post" or bool(image_keys_of(content) or content.video_key))
    words, source = resolve_keywords([], body.title, body.body, None)
    content.title = body.title
    content.body = body.body
    content.bg_style = body.bg_style
    content.summary = body.body[:500]
    content.title_hant = None  # 旧的繁体稿对不上新内容了，回落到简体
    content.summary_hant = None
    content.keywords_json = dump_keywords(words)
    content.keyword_source = source
    content.featured_at = None  # 精选的是改之前的版本
    # 改完按发帖的同一套规则再过一遍：不然先发正常内容、过审后再改成别的，审的和公开的就不是同一个版本。
    # 房间里非房主 / 协作者的帖子回到房主那里；别处的，新用户（过审帖不满 3 条，不算这一条）回到后台；敏感词照拦。
    in_live_room = room is not None and room.is_active
    if content.status == "published" and (
        blocked_term_in(session, body.title, body.body)
        or (in_live_room and not is_room_editor(session, room, user))
        or (not in_live_room and review_on(session, "post", user) and _approved_posts(session, user.id) - 1 < REVIEW_LIMIT)
    ):
        content.status = "pending"
        content.published_at = None  # 重新算作没发布过：房主的投稿队列和后台队列靠它分辨
    write_audit(session, user.id, "content.edit", "content", content.id)
    session.commit()
    return {"content_id": content.id, "status": content.status, "keywords": words}


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
        "bg_style": content.bg_style or "",
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
        "can_edit": user is not None and content.author_id == user.id and content.type in EDITABLE_TYPES,
        "can_delete": user is not None
        and (content.author_id == user.id or (channel is not None and channel.kind == "room" and channel.owner_id == user.id)),
    }


@router.post("/contents/{content_id}/report")
def report_content(
    content_id: str,
    body: ReportBody,
    request: Request,
    user: User | None = Depends(optional_user),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    limit_reports(session, request, user)
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
    cursor: str | None = None,
    limit: int = 50,
    user: User | None = Depends(optional_user),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    content = _visible_content(session, content_id, user)
    visible = (
        RoomComment.content_id == content.id,
        RoomComment.removed_at.is_(None),
        (RoomComment.status == "published")
        | ((RoomComment.status == "pending") & (RoomComment.author_id == (user.id if user else ""))),
    )
    # 按发布顺序一页页给（热门帖几千条回复不能一次全返回）；total 给标题上的「回复 N」用
    bounded = min(max(limit, 1), 100)
    query = select(RoomComment).where(*visible)
    parts = decode_cursor(cursor) if cursor else None
    after_at = parse_added_at(parts[1]) if parts and len(parts) == 2 else None
    if parts and after_at is not None:
        query = query.where(
            or_(RoomComment.created_at > after_at, and_(RoomComment.created_at == after_at, RoomComment.id > parts[0]))
        )
    page_rows = session.scalars(query.order_by(RoomComment.created_at, RoomComment.id).limit(bounded + 1)).all()
    rows = page_rows[:bounded]
    total = int(session.scalar(select(func.count()).select_from(RoomComment).where(*visible)) or 0)
    items: list[dict[str, object]] = []
    counts, liked = comment_like_state(session, user, [row.id for row in rows])
    # 作者和 @ 到的人都整批查：原来每条回复各查一次，热门帖几百条回复就是几百次查询
    authors = author_names(session, [row.author_id for row in rows])
    real_handles = mentioned_handles(session, [row.body for row in rows])
    manages = user is not None and _manages_replies(session, content, user)
    for row in rows:
        author_name, author_handle, author_avatar = authors.get(row.author_id, ("", "", ""))
        items.append(
            {
                "id": row.id,
                "author_id": row.author_id,
                "author_name": author_name,
                "author_handle": author_handle,
                "author_avatar": author_avatar,
                "mentions": [handle for handle in mention_handles(row.body) if handle in real_handles],
                "like_count": counts.get(row.id, 0),
                "liked": row.id in liked,
                "body": row.body,
                "image_key": row.image_key,
                "parent_id": row.parent_id,
                "status": row.status,
                "can_delete": manages or (user is not None and row.author_id == user.id),
                "created_at": row.created_at.isoformat(),
            }
        )
    payload: dict[str, object] = {"items": items, "total": total}
    if len(page_rows) > bounded:
        payload["next_cursor"] = encode_cursor(rows[-1].id, rows[-1].created_at.isoformat())
    return payload


@router.post("/contents/{content_id}/comments")
def create_reply(
    content_id: str,
    body: ReplyBody,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    content = _visible_content(session, content_id, user)
    # 发到「我的动态」的帖子不在任何频道里（item 为空）：照样能回复，只是回复不挂在哪个频道下
    item = session.scalars(select(ChannelItem).where(ChannelItem.content_id == content.id)).first()
    require_not_banned(session, session.scalars(select(ChannelItem.channel_id).where(ChannelItem.content_id == content.id)), user.id)
    parent = None
    if body.parent_id:
        parent = session.get(RoomComment, body.parent_id)
        if parent is None or parent.content_id != content.id or parent.removed_at is not None:
            raise APIError(404, "COMMENT_NOT_FOUND", "要回复的留言不存在")
    require_not_blocked_by(session, [content.author_id, parent.author_id if parent else None], user.id)
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
    # 上面那条只管「同一个帖子」，换着帖子回就没有上限；这里按人封顶
    hourly = session.scalar(
        select(func.count())
        .select_from(RoomComment)
        .where(RoomComment.author_id == user.id, RoomComment.created_at >= now - timedelta(hours=1))
    )
    if (hourly or 0) >= HOURLY_REPLY_LIMIT:
        raise APIError(429, "RATE_LIMITED", "这个小时回复得太多了，请稍后再试")
    comment = RoomComment(
        room_id=item.channel_id if item is not None else None,
        content_id=content.id,
        parent_id=body.parent_id,
        author_id=user.id,
        body=body.body,
        image_key=body.image_key,
        mention_count=mention_count(body.body),
    )
    session.add(comment)
    session.flush()
    if first_status(session, "comment", body.body, user=user) == "published":
        publish_comment(session, comment)  # 给帖子作者的回复通知也在这里面发：待审的回复不通知
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
    if comment.author_id != user.id and not _manages_replies(session, content, user):
        raise APIError(403, "FORBIDDEN", "不能处理这条留言")
    comment.status = "removed"
    comment.removed_at = utcnow()
    write_audit(session, user.id, "comment.remove", "comment", comment.id)
    session.commit()
    return {"comment_id": comment.id, "status": comment.status}


def _manages_replies(session: Session, content: Content, user: User) -> bool:
    """能删这条帖子下别人回复的人：帖子作者，或帖子所在房间的房主。"""
    if content.author_id == user.id:
        return True
    room = _home_room(session, content)
    return room is not None and room.owner_id == user.id


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
    require_not_banned(session, [channel.id], user.id)
    existing = session.scalar(
        select(Content).where(
            Content.author_id == user.id,
            Content.repost_of_id == original.id,
            Content.deleted_at.is_(None),
        )
    )
    if existing is not None:
        return {"content_id": existing.id, "status": existing.status}
    check_hourly_limit(session, user.id)
    now = utcnow()
    note = body.body or original.summary or ""
    # 和发帖同一套规则：新用户前几条要审，附言命中敏感词也先待审（原来转发一律直接公开）
    prior = _approved_posts(session, user.id)
    status = "pending" if review_on(session, "post", user) and (prior or 0) < REVIEW_LIMIT else "published"
    if blocked_term_in(session, body.body):
        status = "pending"
    content = Content(
        type="repost",
        status=status,
        author_id=user.id,
        repost_of_id=original.id,
        title=original.title,
        summary=note[:500],
        body=note,
        source_name=original.source_name,
        licence_ref=original.licence_ref,
        canonical_url=original.canonical_url,
        published_at=now if status == "published" else None,
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
