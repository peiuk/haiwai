"""管理后台接口：除登录外全部要求 User.is_admin，写操作都记审计日志。

审帖 / 审留言 / 审房间 / 处理举报的"决定"接口在 moderation.py，这里只补列表和它没有的操作。
"""
from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.v1.auth import LoginBody, current_user, issue_tokens, throttle
from app.api.v1.channels import TextBody
from app.core.audit import write_audit
from app.core.db import get_db
from app.core.errors import APIError
from app.core.pagination import decode_cursor, encode_cursor, parse_added_at
from app.core.security import verify_password
from app.feed import image_keys_of
from app.models import AuditLog, Channel, ChannelItem, Content, ModerationCase, RoomComment, User, utcnow
from app.reports import REASONS
from app.rooms import drop_pushes, notify_room_update

LIMIT = 50  # 队列、日志每次最多条数
PAGE = 20  # 表格每页条数
TREND_DAYS = 14


def require_admin(user: User = Depends(current_user)) -> User:
    if not user.is_admin:
        raise APIError(403, "FORBIDDEN", "需要管理员权限")
    return user


router = APIRouter(prefix="/admin")
guarded = APIRouter(dependencies=[Depends(require_admin)])  # 文件末尾挂到 router 上


@router.post("/login")
def admin_login(body: LoginBody, session: Session = Depends(get_db)) -> dict[str, str]:
    """后台独立登录：密码对但不是管理员也拒绝，不给普通账号发后台用的令牌。"""
    throttle(f"admin-login:{body.email}", limit=10, window_seconds=15 * 60)
    user = session.scalar(select(User).where(User.email == body.email, User.deleted_at.is_(None)))
    if user is None or not verify_password(body.password, user.password_hash):
        raise APIError(401, "INVALID_CREDENTIALS", "邮箱或密码不正确")
    if not user.is_admin or user.status != "active":
        raise APIError(403, "FORBIDDEN", "这个账号没有后台权限")
    tokens = issue_tokens(session, user.id)
    write_audit(session, user.id, "admin.login", "user", user.id)
    session.commit()
    return tokens


def _names(session: Session, ids) -> dict[str, str]:
    wanted = {item for item in ids if item}
    if not wanted:
        return {}
    rows = session.execute(select(User.id, User.display_name).where(User.id.in_(wanted))).all()
    return {row.id: row.display_name for row in rows}


def _like(value: str) -> str:
    return f"%{value.strip()}%"


def _count(session: Session, model, *where) -> int:
    return int(session.scalar(select(func.count()).select_from(model).where(*where)) or 0)


def _paged(session: Session, query, order, page: int) -> tuple[list, int]:
    total = int(session.scalar(select(func.count()).select_from(query.subquery())) or 0)
    rows = session.scalars(query.order_by(*order).limit(PAGE).offset((max(page, 1) - 1) * PAGE)).all()
    return list(rows), total


def _was_taken_down(session: Session, target_type: str, target_id: str) -> bool:
    """这条内容 / 留言是不是被管理员下架的；作者自己删的不能被后台"复活"。"""
    return (
        session.scalar(
            select(AuditLog.id)
            .where(
                AuditLog.target_type == target_type,
                AuditLog.target_id == target_id,
                AuditLog.action.in_((f"admin.{target_type}.remove", "moderation.remove")),
            )
            .limit(1)
        )
        is not None
    )


def _history(session: Session, target_type: str, target_id: str) -> list[dict[str, object]]:
    """这个对象上发生过的操作（最近 20 条），详情页用。"""
    rows = session.scalars(
        select(AuditLog)
        .where(AuditLog.target_type == target_type, AuditLog.target_id == target_id)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(20)
    ).all()
    names = _names(session, [row.actor_id for row in rows])
    return [
        {"action": row.action, "actor_name": names.get(row.actor_id or "", ""), "detail": row.detail or "", "created_at": row.created_at}
        for row in rows
    ]


def _cases(session: Session, where) -> list[dict[str, object]]:
    rows = session.scalars(select(ModerationCase).where(where).order_by(ModerationCase.created_at.desc()).limit(20)).all()
    names = _names(session, [row.reporter_id for row in rows])
    return [
        {
            "case_id": row.id,
            "reason": REASONS.get(row.reason, row.reason),
            "detail": row.detail,
            "status": row.status,
            "decision": row.decision or "",
            "reporter_name": names.get(row.reporter_id or "", ""),
            "created_at": row.created_at,
        }
        for row in rows
    ]


_PENDING_CONTENT = (Content.status == "pending", Content.deleted_at.is_(None))
_PENDING_COMMENT = (RoomComment.status == "pending", RoomComment.removed_at.is_(None))
_PENDING_CHANNEL = (Channel.review_status == "pending", Channel.owner_id.is_not(None))


@guarded.get("/stats")
def stats(session: Session = Depends(get_db)) -> dict[str, object]:
    today = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)  # UTC 当天
    since = today - timedelta(days=TREND_DAYS - 1)
    # shortcut: 把近 14 天的时间戳取回来在内存里按天数，量大了再换成按日期分组的 SQL。
    posts = session.scalars(select(Content.created_at).where(Content.created_at >= since, Content.author_id.is_not(None))).all()
    users = session.scalars(select(User.created_at).where(User.created_at >= since)).all()
    days = [(since + timedelta(days=index)).date() for index in range(TREND_DAYS)]
    post_days = [item.date() for item in posts]
    user_days = [item.date() for item in users]
    return {
        "new_posts_today": post_days.count(today.date()),
        "new_users_today": user_days.count(today.date()),
        "pending_contents": _count(session, Content, *_PENDING_CONTENT),
        "pending_comments": _count(session, RoomComment, *_PENDING_COMMENT),
        "pending_channels": _count(session, Channel, *_PENDING_CHANNEL),
        "open_cases": _count(session, ModerationCase, ModerationCase.status == "open"),
        "total_users": _count(session, User, User.deleted_at.is_(None)),
        "total_contents": _count(session, Content, Content.status == "published"),
        "trend": [
            {"date": day.isoformat(), "posts": post_days.count(day), "users": user_days.count(day)} for day in days
        ],
    }


def _case_target(session: Session, case: ModerationCase) -> tuple[str, str | None, str]:
    # 分支顺序与 moderation.decide_case 一致，保证这里显示的对象就是决定时处理的对象。
    if case.reported_comment_id:
        comment = session.get(RoomComment, case.reported_comment_id)
        return "comment", case.reported_comment_id, (comment.body[:80] or "（图片留言）") if comment else "（留言已不存在）"
    if case.reported_channel_id and case.content_id is None and case.reported_user_id is None:
        channel = session.get(Channel, case.reported_channel_id)
        return "channel", case.reported_channel_id, channel.name_hans if channel else "（房间已不存在）"
    if case.reported_user_id and case.content_id is None:
        reported = session.get(User, case.reported_user_id)
        return "user", case.reported_user_id, reported.display_name if reported else "（用户已不存在）"
    content = session.get(Content, case.content_id) if case.content_id else None
    return "content", case.content_id, content.title if content else "（内容已不存在）"


@guarded.get("/queue")
def queue(session: Session = Depends(get_db)) -> dict[str, list[dict[str, object]]]:
    contents = session.scalars(select(Content).where(*_PENDING_CONTENT).order_by(Content.created_at).limit(LIMIT)).all()
    comments = session.scalars(
        select(RoomComment).where(*_PENDING_COMMENT).order_by(RoomComment.created_at).limit(LIMIT)
    ).all()
    channels = session.scalars(select(Channel).where(*_PENDING_CHANNEL).order_by(Channel.created_at).limit(LIMIT)).all()
    cases = session.scalars(
        select(ModerationCase).where(ModerationCase.status == "open").order_by(ModerationCase.created_at).limit(LIMIT)
    ).all()
    names = _names(
        session,
        [row.author_id for row in contents]
        + [row.author_id for row in comments]
        + [row.owner_id for row in channels]
        + [row.reporter_id for row in cases],
    )
    case_rows = []
    for case in cases:
        target_type, target_id, label = _case_target(session, case)
        case_rows.append(
            {
                "case_id": case.id,
                "target_type": target_type,
                "target_id": target_id,
                "target_label": label,
                "reason": REASONS.get(case.reason, case.reason),
                "detail": case.detail,
                "reporter_name": names.get(case.reporter_id or "", ""),
                "created_at": case.created_at,
            }
        )
    return {
        "contents": [
            {
                "content_id": row.id,
                "title": row.title,
                "summary": row.summary or (row.body or "")[:200],
                "author_name": names.get(row.author_id or "", ""),
                "created_at": row.created_at,
            }
            for row in contents
        ],
        "comments": [
            {
                "comment_id": row.id,
                "content_id": row.content_id,
                "body": row.body,
                "author_name": names.get(row.author_id, ""),
                "created_at": row.created_at,
            }
            for row in comments
        ],
        "channels": [
            {
                "channel_id": row.id,
                "name": row.name_hans,
                "owner_name": names.get(row.owner_id or "", ""),
                "created_at": row.created_at,
            }
            for row in channels
        ],
        "cases": case_rows,
    }


@guarded.get("/users")
def list_users(q: str = "", status: str = "", page: int = 1, session: Session = Depends(get_db)) -> dict[str, object]:
    query = select(User).where(User.deleted_at.is_(None))
    if q.strip():
        like = _like(q)
        query = query.where(or_(User.email.ilike(like), User.display_name.ilike(like), User.handle.ilike(like)))
    if status:
        query = query.where(User.status == status)
    rows, total = _paged(session, query, (User.created_at.desc(), User.id), page)
    counts = dict(
        session.execute(
            select(Content.author_id, func.count())
            .where(Content.author_id.in_([row.id for row in rows]), Content.deleted_at.is_(None))
            .group_by(Content.author_id)
        ).all()
    )
    return {
        "total": total,
        "page_size": PAGE,
        "items": [
            {
                "user_id": row.id,
                "display_name": row.display_name,
                "handle": row.handle or "",
                "email": row.email,
                "status": row.status,
                "is_admin": row.is_admin,
                "post_count": counts.get(row.id, 0),
                "created_at": row.created_at,
            }
            for row in rows
        ],
    }


class Reasoned(BaseModel):
    reason: str = Field(default="", max_length=300)  # 操作理由，记入审计日志

    @property
    def note(self) -> str | None:
        return self.reason.strip() or None


class UserStatusBody(Reasoned):
    status: Literal["active", "suspended"]


@guarded.get("/users/{user_id}")
def user_detail(user_id: str, session: Session = Depends(get_db)) -> dict[str, object]:
    target = session.get(User, user_id)
    if target is None:
        raise APIError(404, "USER_NOT_FOUND", "用户不存在")
    posts = session.scalars(
        select(Content).where(Content.author_id == target.id).order_by(Content.created_at.desc()).limit(10)
    ).all()
    return {
        "user_id": target.id,
        "display_name": target.display_name,
        "handle": target.handle or "",
        "email": target.email,
        "city_label": target.city_label or "",
        "phone_verified": target.phone_verified,
        "status": target.status,
        "is_admin": target.is_admin,
        "created_at": target.created_at,
        "post_count": _count(session, Content, Content.author_id == target.id, Content.deleted_at.is_(None)),
        "comment_count": _count(session, RoomComment, RoomComment.author_id == target.id, RoomComment.removed_at.is_(None)),
        "posts": [
            {"content_id": row.id, "title": row.title, "type": row.type, "status": row.status, "created_at": row.created_at}
            for row in posts
        ],
        "cases": _cases(session, ModerationCase.reported_user_id == target.id),
        "history": _history(session, "user", target.id),
    }


class AdminFlagBody(Reasoned):
    is_admin: bool


@guarded.post("/users/{user_id}/admin")
def set_user_admin(
    user_id: str,
    body: AdminFlagBody,
    admin: User = Depends(require_admin),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    target = session.get(User, user_id)
    if target is None or target.deleted_at is not None:
        raise APIError(404, "USER_NOT_FOUND", "用户不存在")
    if target.id == admin.id:
        raise APIError(409, "CANNOT_CHANGE_SELF", "不能修改自己的管理员权限")  # 免得最后一个管理员把自己撤掉
    if target.is_admin == body.is_admin:
        raise APIError(409, "NO_CHANGE", "已经是这个状态")
    if body.is_admin and target.status != "active":
        raise APIError(409, "NO_CHANGE", "被封禁的账号不能设为管理员")
    target.is_admin = body.is_admin
    write_audit(session, admin.id, "admin.user.grant" if body.is_admin else "admin.user.revoke", "user", target.id, body.note)
    session.commit()
    return {"user_id": target.id, "is_admin": target.is_admin}


@guarded.post("/users/{user_id}/status")
def set_user_status(
    user_id: str,
    body: UserStatusBody,
    admin: User = Depends(require_admin),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    target = session.get(User, user_id)
    if target is None or target.deleted_at is not None:
        raise APIError(404, "USER_NOT_FOUND", "用户不存在")
    # 不能封自己或其他管理员，免得后台被锁死；要处理管理员先用命令行撤销权限。
    if body.status == "suspended" and (target.id == admin.id or target.is_admin):
        raise APIError(409, "CANNOT_SUSPEND_ADMIN", "不能封禁管理员")
    if target.status == body.status:
        raise APIError(409, "NO_CHANGE", "已经是这个状态")
    target.status = body.status
    action = "admin.user.suspend" if body.status == "suspended" else "admin.user.activate"
    write_audit(session, admin.id, action, "user", target.id, body.note)
    session.commit()
    return {"user_id": target.id, "status": target.status}


@guarded.get("/contents")
def list_contents(
    q: str = "",
    status: str = "",
    type: str = "",
    page: int = 1,
    session: Session = Depends(get_db),
) -> dict[str, object]:
    query = select(Content)
    if q.strip():
        query = query.where(Content.title.ilike(_like(q)))
    if status:
        query = query.where(Content.status == status)
    types = [item for item in type.split(",") if item]  # 逗号分隔，如 news,announcement,topic
    if types:
        query = query.where(Content.type.in_(types))
    rows, total = _paged(session, query, (Content.created_at.desc(), Content.id), page)
    names = _names(session, [row.author_id for row in rows])
    channels = dict(
        session.execute(
            select(ChannelItem.content_id, Channel.name_hans)
            .join(Channel, Channel.id == ChannelItem.channel_id)
            .where(ChannelItem.content_id.in_([row.id for row in rows]))
        ).all()
    )
    return {
        "total": total,
        "page_size": PAGE,
        "items": [
            {
                "content_id": row.id,
                "title": row.title,
                "type": row.type,
                "status": row.status,
                "author_name": names.get(row.author_id or "", row.source_name or ""),
                "channel_name": channels.get(row.id, ""),
                "view_count": row.view_count or 0,
                "featured": row.featured_at is not None,
                "created_at": row.created_at,
            }
            for row in rows
        ],
    }


@guarded.get("/contents/{content_id}")
def content_detail(content_id: str, session: Session = Depends(get_db)) -> dict[str, object]:
    content = session.get(Content, content_id)
    if content is None:
        raise APIError(404, "CONTENT_NOT_FOUND", "内容不存在")
    author = session.get(User, content.author_id) if content.author_id else None
    channel = session.scalar(
        select(Channel).join(ChannelItem, ChannelItem.channel_id == Channel.id).where(ChannelItem.content_id == content.id).limit(1)
    )
    return {
        "content_id": content.id,
        "title": content.title,
        "body": content.body or content.summary or "",
        "type": content.type,
        "status": content.status,
        "author_id": content.author_id,
        "author_name": author.display_name if author else content.source_name or "",
        "channel_name": channel.name_hans if channel else "",
        "image_urls": [f"/api/v1/uploads/{key}" for key in image_keys_of(content)],
        "has_video": bool(content.video_key or content.embed_media_id),
        "canonical_url": content.canonical_url or "",
        "view_count": content.view_count or 0,
        "featured": content.featured_at is not None,
        "created_at": content.created_at,
        "comment_count": _count(session, RoomComment, RoomComment.content_id == content.id, RoomComment.removed_at.is_(None)),
        "cases": _cases(session, ModerationCase.content_id == content.id),
        "history": _history(session, "content", content.id),
    }


class FeaturedBody(BaseModel):
    featured: bool


@guarded.post("/contents/{content_id}/featured")
def set_content_featured(
    content_id: str,
    body: FeaturedBody,
    admin: User = Depends(require_admin),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    content = session.get(Content, content_id)
    if content is None:
        raise APIError(404, "CONTENT_NOT_FOUND", "内容不存在")
    if body.featured and content.status != "published":
        raise APIError(409, "NO_CHANGE", "只有已发布的内容可以设为精选")
    if (content.featured_at is not None) == body.featured:
        raise APIError(409, "NO_CHANGE", "已经是这个状态")
    content.featured_at = utcnow() if body.featured else None
    write_audit(session, admin.id, "admin.content.feature" if body.featured else "admin.content.unfeature", "content", content.id)
    session.commit()
    return {"content_id": content.id, "featured": body.featured}


class AnnouncementBody(TextBody):
    channel_id: str


@guarded.post("/announcements")
def publish_announcement(
    body: AnnouncementBody,
    admin: User = Depends(require_admin),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    """以后台身份在任意上架的频道里发一条置顶公告。"""
    channel = session.get(Channel, body.channel_id)
    if channel is None or not channel.is_active:
        raise APIError(404, "CHANNEL_NOT_FOUND", "频道不存在或已下架")
    now = utcnow()
    content = Content(
        type="announcement",
        status="published",
        author_id=admin.id,
        title=body.title,
        summary=body.body[:500],
        body=body.body,
        source_name="海外圈官方",
        published_at=now,
    )
    session.add(content)
    session.flush()
    session.add(ChannelItem(channel_id=channel.id, content_id=content.id, pinned=True, added_at=now))
    notify_room_update(session, channel, content)
    write_audit(session, admin.id, "admin.announcement.create", "content", content.id)
    session.commit()
    return {"content_id": content.id, "status": content.status}


class TakedownBody(Reasoned):
    action: Literal["remove", "restore"]


@guarded.post("/contents/{content_id}/status")
def set_content_status(
    content_id: str,
    body: TakedownBody,
    admin: User = Depends(require_admin),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    content = session.get(Content, content_id)
    if content is None:
        raise APIError(404, "CONTENT_NOT_FOUND", "内容不存在")
    if body.action == "remove":
        if content.status == "deleted":
            raise APIError(409, "NO_CHANGE", "这条内容已经下架")
        content.status = "deleted"
        content.deleted_at = utcnow()
        drop_pushes(session, content.id)
    else:
        if content.status != "deleted" or not _was_taken_down(session, "content", content.id):
            raise APIError(409, "NO_CHANGE", "这条内容不是被管理员下架的，不能恢复")
        content.status = "published"
        content.deleted_at = None
    write_audit(session, admin.id, f"admin.content.{body.action}", "content", content.id, body.note)
    session.commit()
    return {"content_id": content.id, "status": content.status}


@guarded.get("/comments")
def list_comments(q: str = "", status: str = "", page: int = 1, session: Session = Depends(get_db)) -> dict[str, object]:
    query = select(RoomComment)
    if q.strip():
        query = query.where(RoomComment.body.ilike(_like(q)))
    if status:
        query = query.where(RoomComment.status == status)
    rows, total = _paged(session, query, (RoomComment.created_at.desc(), RoomComment.id), page)
    names = _names(session, [row.author_id for row in rows])
    rooms = dict(
        session.execute(select(Channel.id, Channel.name_hans).where(Channel.id.in_([row.room_id for row in rows]))).all()
    )
    titles = dict(
        session.execute(select(Content.id, Content.title).where(Content.id.in_([row.content_id for row in rows if row.content_id]))).all()
    )
    return {
        "total": total,
        "page_size": PAGE,
        "items": [
            {
                "comment_id": row.id,
                "body": row.body,
                "has_image": bool(row.image_key),
                "status": row.status,
                "author_name": names.get(row.author_id, ""),
                "room_name": rooms.get(row.room_id, ""),
                "content_id": row.content_id,
                "content_title": titles.get(row.content_id or "", ""),
                "created_at": row.created_at,
            }
            for row in rows
        ],
    }


@guarded.post("/comments/{comment_id}/status")
def set_comment_status(
    comment_id: str,
    body: TakedownBody,
    admin: User = Depends(require_admin),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    comment = session.get(RoomComment, comment_id)
    if comment is None:
        raise APIError(404, "COMMENT_NOT_FOUND", "留言不存在")
    if body.action == "remove":
        if comment.status == "removed":
            raise APIError(409, "NO_CHANGE", "这条留言已经删除")
        comment.status = "removed"
        comment.removed_at = utcnow()
    else:
        if comment.status != "removed" or not _was_taken_down(session, "comment", comment.id):
            raise APIError(409, "NO_CHANGE", "这条留言不是被管理员删除的，不能恢复")
        comment.status = "published"
        comment.removed_at = None
    write_audit(session, admin.id, f"admin.comment.{body.action}", "comment", comment.id, body.note)
    session.commit()
    return {"comment_id": comment.id, "status": comment.status}


@guarded.get("/channels")
def list_channels(q: str = "", page: int = 1, session: Session = Depends(get_db)) -> dict[str, object]:
    query = select(Channel)
    if q.strip():
        like = _like(q)
        query = query.where(or_(Channel.name_hans.ilike(like), Channel.code.ilike(like)))
    rows, total = _paged(session, query, (Channel.created_at.desc(), Channel.id), page)
    names = _names(session, [row.owner_id for row in rows])
    return {
        "total": total,
        "page_size": PAGE,
        "items": [
            {
                "channel_id": row.id,
                "code": row.code,
                "name": row.name_hans,
                "kind": row.kind,
                "owner_name": names.get(row.owner_id or "", ""),
                "is_active": row.is_active,
                "is_certified": row.is_certified,
                "certified": row.certified,
                "review_status": row.review_status,
                "subscriber_count": row.subscriber_count,
                "created_at": row.created_at,
            }
            for row in rows
        ],
    }


@guarded.get("/channel-options")
def channel_options(session: Session = Depends(get_db)) -> dict[str, list[dict[str, str]]]:
    """发公告时选频道用：所有上架的频道。"""
    rows = session.execute(
        select(Channel.id, Channel.name_hans).where(Channel.is_active.is_(True)).order_by(Channel.kind, Channel.name_hans).limit(200)
    ).all()
    return {"items": [{"channel_id": row.id, "name": row.name_hans} for row in rows]}


class CertifiedBody(BaseModel):
    certified: bool


@guarded.post("/channels/{channel_id}/certified")
def set_channel_certified(
    channel_id: str,
    body: CertifiedBody,
    admin: User = Depends(require_admin),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    channel = session.get(Channel, channel_id)
    if channel is None:
        raise APIError(404, "CHANNEL_NOT_FOUND", "频道不存在")
    if (channel.kind or "").startswith("official"):
        raise APIError(409, "NO_CHANGE", "官方频道本来就带认证")
    if channel.is_certified == body.certified:
        raise APIError(409, "NO_CHANGE", "已经是这个状态")
    channel.is_certified = body.certified
    write_audit(session, admin.id, "admin.channel.certify" if body.certified else "admin.channel.uncertify", "channel", channel.id)
    session.commit()
    return {"channel_id": channel.id, "certified": channel.certified}


class ChannelActiveBody(Reasoned):
    active: bool


@guarded.post("/channels/{channel_id}/active")
def set_channel_active(
    channel_id: str,
    body: ChannelActiveBody,
    admin: User = Depends(require_admin),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    channel = session.get(Channel, channel_id)
    if channel is None:
        raise APIError(404, "CHANNEL_NOT_FOUND", "频道不存在")
    if channel.is_active == body.active:
        raise APIError(409, "NO_CHANGE", "已经是这个状态")
    channel.is_active = body.active
    action = "admin.channel.activate" if body.active else "admin.channel.deactivate"
    write_audit(session, admin.id, action, "channel", channel.id, body.note)
    session.commit()
    return {"channel_id": channel.id, "is_active": channel.is_active}


@guarded.get("/audit")
def list_audit(action: str = "", cursor: str = "", session: Session = Depends(get_db)) -> dict[str, object]:
    query = select(AuditLog)
    if action.strip():
        query = query.where(AuditLog.action.ilike(_like(action)))
    parts = decode_cursor(cursor) if cursor else None
    at: datetime | None = parse_added_at(parts[0]) if parts and len(parts) == 2 else None
    if at is not None:
        query = query.where(or_(AuditLog.created_at < at, (AuditLog.created_at == at) & (AuditLog.id < parts[1])))
    rows = session.scalars(query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(LIMIT + 1)).all()
    page = rows[:LIMIT]
    names = _names(session, [row.actor_id for row in page])
    return {
        "items": [
            {
                "id": row.id,
                "action": row.action,
                "actor_name": names.get(row.actor_id or "", ""),
                "target_type": row.target_type,
                "target_id": row.target_id,
                "detail": row.detail or "",
                "created_at": row.created_at,
            }
            for row in page
        ],
        "next_cursor": encode_cursor(page[-1].created_at.isoformat(), page[-1].id) if len(rows) > LIMIT else None,
    }


router.include_router(guarded)
