"""管理后台接口：全部要求 User.is_admin，写操作都记审计日志。

审帖 / 审留言 / 审房间 / 处理举报的"决定"接口在 moderation.py，这里只补列表和它没有的操作。
"""
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.v1.auth import current_user
from app.core.audit import write_audit
from app.core.db import get_db
from app.core.errors import APIError
from app.core.pagination import decode_cursor, encode_cursor, parse_added_at
from app.models import AuditLog, Channel, Content, ModerationCase, RoomComment, User, utcnow
from app.reports import REASONS
from app.rooms import drop_pushes

LIMIT = 50


def require_admin(user: User = Depends(current_user)) -> User:
    if not user.is_admin:
        raise APIError(403, "FORBIDDEN", "需要管理员权限")
    return user


router = APIRouter(prefix="/admin", dependencies=[Depends(require_admin)])


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


_PENDING_CONTENT = (Content.status == "pending", Content.deleted_at.is_(None))
_PENDING_COMMENT = (RoomComment.status == "pending", RoomComment.removed_at.is_(None))
_PENDING_CHANNEL = (Channel.review_status == "pending", Channel.owner_id.is_not(None))


@router.get("/stats")
def stats(session: Session = Depends(get_db)) -> dict[str, int]:
    today = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)  # UTC 当天
    return {
        "new_posts_today": _count(session, Content, Content.created_at >= today, Content.author_id.is_not(None)),
        "new_users_today": _count(session, User, User.created_at >= today),
        "pending_contents": _count(session, Content, *_PENDING_CONTENT),
        "pending_comments": _count(session, RoomComment, *_PENDING_COMMENT),
        "pending_channels": _count(session, Channel, *_PENDING_CHANNEL),
        "open_cases": _count(session, ModerationCase, ModerationCase.status == "open"),
    }


def _case_target(session: Session, case: ModerationCase) -> tuple[str, str | None, str]:
    # 分支顺序与 moderation.decide_case 一致，保证这里显示的对象就是决定时处理的对象。
    if case.reported_comment_id:
        comment = session.get(RoomComment, case.reported_comment_id)
        return "comment", case.reported_comment_id, comment.body[:80] if comment else "（留言已不存在）"
    if case.reported_channel_id and case.content_id is None and case.reported_user_id is None:
        channel = session.get(Channel, case.reported_channel_id)
        return "channel", case.reported_channel_id, channel.name_hans if channel else "（房间已不存在）"
    if case.reported_user_id and case.content_id is None:
        reported = session.get(User, case.reported_user_id)
        return "user", case.reported_user_id, reported.display_name if reported else "（用户已不存在）"
    content = session.get(Content, case.content_id) if case.content_id else None
    return "content", case.content_id, content.title if content else "（内容已不存在）"


@router.get("/queue")
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


@router.get("/users")
def list_users(q: str = "", session: Session = Depends(get_db)) -> dict[str, list[dict[str, object]]]:
    query = select(User).where(User.deleted_at.is_(None))
    if q.strip():
        like = _like(q)
        query = query.where(or_(User.email.ilike(like), User.display_name.ilike(like), User.handle.ilike(like)))
    rows = session.scalars(query.order_by(User.created_at.desc()).limit(LIMIT)).all()
    return {
        "items": [
            {
                "user_id": row.id,
                "display_name": row.display_name,
                "handle": row.handle or "",
                "email": row.email,
                "status": row.status,
                "is_admin": row.is_admin,
                "created_at": row.created_at,
            }
            for row in rows
        ]
    }


class UserStatusBody(BaseModel):
    status: Literal["active", "suspended"]


@router.post("/users/{user_id}/status")
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
    write_audit(session, admin.id, action, "user", target.id)
    session.commit()
    return {"user_id": target.id, "status": target.status}


@router.get("/contents")
def list_contents(q: str = "", status: str = "", session: Session = Depends(get_db)) -> dict[str, list[dict[str, object]]]:
    query = select(Content)
    if q.strip():
        query = query.where(Content.title.ilike(_like(q)))
    if status:
        query = query.where(Content.status == status)
    rows = session.scalars(query.order_by(Content.created_at.desc()).limit(LIMIT)).all()
    names = _names(session, [row.author_id for row in rows])
    return {
        "items": [
            {
                "content_id": row.id,
                "title": row.title,
                "type": row.type,
                "status": row.status,
                "author_name": names.get(row.author_id or "", row.source_name or ""),
                "created_at": row.created_at,
            }
            for row in rows
        ]
    }


class ContentStatusBody(BaseModel):
    action: Literal["remove", "restore"]


@router.post("/contents/{content_id}/status")
def set_content_status(
    content_id: str,
    body: ContentStatusBody,
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
        # 只恢复管理员下架的；作者自己删的不能被后台"复活"。
        taken_down = session.scalar(
            select(AuditLog.id)
            .where(
                AuditLog.target_type == "content",
                AuditLog.target_id == content.id,
                AuditLog.action.in_(("admin.content.remove", "moderation.remove")),
            )
            .limit(1)
        )
        if content.status != "deleted" or taken_down is None:
            raise APIError(409, "NO_CHANGE", "这条内容不是被管理员下架的，不能恢复")
        content.status = "published"
        content.deleted_at = None
    write_audit(session, admin.id, f"admin.content.{body.action}", "content", content.id)
    session.commit()
    return {"content_id": content.id, "status": content.status}


@router.get("/channels")
def list_channels(q: str = "", session: Session = Depends(get_db)) -> dict[str, list[dict[str, object]]]:
    query = select(Channel)
    if q.strip():
        like = _like(q)
        query = query.where(or_(Channel.name_hans.ilike(like), Channel.code.ilike(like)))
    rows = session.scalars(query.order_by(Channel.created_at.desc()).limit(LIMIT)).all()
    return {
        "items": [
            {
                "channel_id": row.id,
                "code": row.code,
                "name": row.name_hans,
                "kind": row.kind,
                "is_active": row.is_active,
                "review_status": row.review_status,
                "subscriber_count": row.subscriber_count,
            }
            for row in rows
        ]
    }


class ChannelActiveBody(BaseModel):
    active: bool


@router.post("/channels/{channel_id}/active")
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
    write_audit(session, admin.id, action, "channel", channel.id)
    session.commit()
    return {"channel_id": channel.id, "is_active": channel.is_active}


@router.get("/audit")
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
                "created_at": row.created_at,
            }
            for row in page
        ],
        "next_cursor": encode_cursor(page[-1].created_at.isoformat(), page[-1].id) if len(rows) > LIMIT else None,
    }
