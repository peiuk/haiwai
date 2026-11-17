"""管理后台接口：除登录外全部要求 User.is_admin，写操作都记审计日志。

审帖 / 审留言 / 审房间 / 处理举报的"决定"接口在 moderation.py，这里只补列表和它没有的操作。
"""
import time
from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.api.v1.auth import LoginBody, bearer, current_user, issue_tokens, throttle
from app.api.v1.channels import TextBody
from app.api.v1.uploads import delete_object
from app.core.audit import client_ip, recent_server_errors, write_audit
from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import APIError
from app.core.pagination import decode_cursor, encode_cursor, parse_added_at
from app.core.security import hash_refresh_token, new_refresh_token, token_is_admin, verify_password, verify_totp
from app.feed import image_keys_of
from app.models import (
    AuditLog,
    Channel,
    ChannelItem,
    CommentLike,
    ContactView,
    Content,
    ContentReaction,
    ListingExt,
    ModerationCase,
    Notification,
    PasswordReset,
    RefreshSession,
    ReviewClaim,
    RoomComment,
    RoomPostPush,
    UploadObject,
    User,
    UserItemProgress,
    utcnow,
)
from app.reports import REASONS
from app.rooms import drop_pushes, notify_room_update

LIMIT = 50  # 队列、日志每次最多条数
PAGE = 20  # 表格每页条数
TREND_DAYS = 14


def require_admin(
    user: User = Depends(current_user),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> User:
    if not user.is_admin:
        raise APIError(403, "FORBIDDEN", "需要管理员权限")
    # 只认后台登录发的令牌：前台登录没过两步验证，它的令牌不能用来操作后台
    if credentials is None or not token_is_admin(credentials.credentials):
        raise APIError(401, "ADMIN_LOGIN_REQUIRED", "请从后台登录页登录")
    return user


def require_super(admin: User = Depends(require_admin)) -> User:
    """超级管理员才能做的事：彻底删除、管理频道和国家、任免管理员、导出数据。"""
    if not admin.is_super:
        raise APIError(403, "SUPER_ONLY", "这项操作需要超级管理员权限")
    return admin


router = APIRouter(prefix="/admin")
guarded = APIRouter(dependencies=[Depends(require_admin)])  # 文件末尾挂到 router 上


class AdminLoginBody(LoginBody):
    code: str = ""  # 开了两步验证的账号要带验证器 App 上的 6 位数字


@router.post("/login")
def admin_login(body: AdminLoginBody, request: Request, session: Session = Depends(get_db)) -> dict[str, str]:
    """后台独立登录：密码对但不是管理员也拒绝，不给普通账号发后台用的令牌。"""
    throttle(session, f"admin-login:{body.email}", limit=10, window_seconds=15 * 60)
    # 同一个来源换着邮箱试也要拦
    throttle(session, f"admin-login-ip:{client_ip(request)}", limit=30, window_seconds=15 * 60)
    user = session.scalar(select(User).where(User.email == body.email, User.deleted_at.is_(None)))
    if user is None or not verify_password(body.password, user.password_hash):
        raise APIError(401, "INVALID_CREDENTIALS", "邮箱或密码不正确")
    if not user.is_admin or user.status != "active":
        raise APIError(403, "FORBIDDEN", "这个账号没有后台权限")
    if user.totp_secret:
        if not body.code.strip():
            raise APIError(401, "TOTP_REQUIRED", "请输入验证器 App 上的 6 位验证码")
        if not verify_totp(user.totp_secret, body.code):
            raise APIError(401, "TOTP_INVALID", "验证码不正确或已过期")
    tokens = issue_tokens(session, user.id, admin=True)
    write_audit(session, user.id, "admin.login", "user", user.id)
    session.commit()
    return tokens


def notify_user(session: Session, user_id: str | None, body: str, content_id: str | None = None, actor_id: str | None = None) -> None:
    """把后台的处理结果告诉当事人（出现在对方的通知里）。自己处理自己的内容不用通知。"""
    if user_id and user_id != actor_id:
        session.add(Notification(user_id=user_id, kind="moderation.notice", body=body[:200], content_id=content_id))


def _because(note: str | None) -> str:
    return f"。原因：{note}" if note else ""


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
_PENDING_CHANNEL = (
    Channel.review_status == "pending",
    Channel.owner_id.is_not(None),
    # 房主已注销的不用再审（注销时会一并标成被拒；这条兜住之前留下的）
    Channel.owner_id.not_in(select(User.id).where(User.deleted_at.is_not(None))),
)


INSIGHT_SECONDS = 60
OVERDUE_HOURS = 24  # 举报和待审超过这么久没处理就算超时（前台对举报人承诺的是 24 小时内处理）
_insight_cache: tuple[float, dict[str, object]] | None = None


def _insights(session: Session) -> dict[str, object]:
    """概览页的趋势和运营指标。算起来要扫近 30 天的数据，所以缓存一分钟；待办数字不走这里，始终是实时的。"""
    global _insight_cache
    if _insight_cache is not None and time.monotonic() - _insight_cache[0] < INSIGHT_SECONDS and not get_settings().testing:
        return _insight_cache[1]
    now = utcnow()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)  # UTC 当天
    since = today - timedelta(days=TREND_DAYS - 1)
    month = now - timedelta(days=30)
    # shortcut: 把近 14 天的时间戳取回来在内存里按天数，量大了再换成按日期分组的 SQL。
    posts = session.scalars(select(Content.created_at).where(Content.created_at >= since, Content.author_id.is_not(None))).all()
    users = session.scalars(select(User.created_at).where(User.created_at >= since)).all()
    days = [(since + timedelta(days=index)).date() for index in range(TREND_DAYS)]
    post_days = [item.date() for item in posts]
    user_days = [item.date() for item in users]
    # 审核用时：近 30 天里，从发布到被审（通过或拒绝）隔了多久
    reviewed = session.execute(
        select(AuditLog.created_at, Content.created_at)
        .join(Content, Content.id == AuditLog.target_id)
        .where(
            AuditLog.action.in_(("moderation.approve", "moderation.reject")),
            AuditLog.target_type == "content",
            AuditLog.created_at >= month,
        )
        .limit(500)
    ).all()
    hours = [(decided - created).total_seconds() / 3600 for decided, created in reviewed]
    closed = _count(session, ModerationCase, ModerationCase.status == "closed", ModerationCase.decided_at >= month)
    upheld = _count(
        session, ModerationCase, ModerationCase.status == "closed", ModerationCase.decided_at >= month, ModerationCase.decision == "remove"
    )
    by_region = session.execute(
        select(Channel.region_code, func.count(func.distinct(ChannelItem.content_id)))
        .join(ChannelItem, ChannelItem.channel_id == Channel.id)
        .join(Content, Content.id == ChannelItem.content_id)
        .where(Content.created_at >= since, Content.status == "published")
        .group_by(Channel.region_code)
        .order_by(func.count(func.distinct(ChannelItem.content_id)).desc())
    ).all()
    result: dict[str, object] = {
        "new_posts_today": post_days.count(today.date()),
        "new_users_today": user_days.count(today.date()),
        "trend": [{"date": day.isoformat(), "posts": post_days.count(day), "users": user_days.count(day)} for day in days],
        "active_users_7d": _count(session, User, User.feed_seen_at >= now - timedelta(days=7)),
        "avg_review_hours": round(sum(hours) / len(hours), 1) if hours else None,
        "cases_closed_30d": closed,
        "cases_upheld_30d": upheld,
        "posts_by_region": [{"region": code, "posts": count} for code, count in by_region],
        "server_errors_1h": recent_server_errors(),
    }
    _insight_cache = (time.monotonic(), result)
    return result


@guarded.get("/stats")
def stats(session: Session = Depends(get_db)) -> dict[str, object]:
    overdue = utcnow() - timedelta(hours=OVERDUE_HOURS)
    return {
        **_insights(session),
        "pending_contents": _count(session, Content, *_PENDING_CONTENT),
        "pending_comments": _count(session, RoomComment, *_PENDING_COMMENT),
        "pending_channels": _count(session, Channel, *_PENDING_CHANNEL),
        "open_cases": _count(session, ModerationCase, ModerationCase.status == "open"),
        "overdue_cases": _count(session, ModerationCase, ModerationCase.status == "open", ModerationCase.created_at < overdue),
        "overdue_contents": _count(session, Content, *_PENDING_CONTENT, Content.created_at < overdue),
        "total_users": _count(session, User, User.deleted_at.is_(None)),
        "total_contents": _count(session, Content, Content.status == "published"),
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


CLAIM_MINUTES = 10


def active_claims(session: Session) -> dict[tuple[str, str], str]:
    """还在有效期内的认领：(对象类型, 对象 id) → 认领的管理员 id。"""
    fresh = utcnow() - timedelta(minutes=CLAIM_MINUTES)
    rows = session.scalars(select(ReviewClaim).where(ReviewClaim.claimed_at >= fresh)).all()
    return {(row.target_type, row.target_id): row.admin_id for row in rows}


@guarded.get("/queue")
def queue(admin: User = Depends(require_admin), session: Session = Depends(get_db)) -> dict[str, list[dict[str, object]]]:
    claims = active_claims(session)
    claimers = _names(session, claims.values())

    def claimed_by(target_type: str, target_id: str) -> str:
        """别的管理员正在处理这一条时返回对方的名字；没人认领或是自己认领的返回空串。"""
        holder = claims.get((target_type, target_id))
        return claimers.get(holder, "其他管理员") if holder and holder != admin.id else ""

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
                "claimed_by": claimed_by("case", case.id),
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
                # AI 资讯稿：没有作者；数字和原文对不上时标「待核对」，审核时点原文对一下
                "ai_draft": row.author_id is None and row.source_name == "GOV.UK",
                "ai_check": row.ai_status == "check",
                "source_url": row.canonical_url,
                "claimed_by": claimed_by("content", row.id),
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
                "claimed_by": claimed_by("comment", row.id),
                "created_at": row.created_at,
            }
            for row in comments
        ],
        "channels": [
            {
                "channel_id": row.id,
                "name": row.name_hans,
                "owner_name": names.get(row.owner_id or "", ""),
                "claimed_by": claimed_by("channel", row.id),
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
                "suspended_until": row.suspended_until,
                "is_admin": row.is_admin,
                "is_super": row.is_super,
                "is_trusted": row.is_trusted,
                "two_factor": bool(row.totp_secret),
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
    days: int | None = Field(default=None, ge=1, le=365)  # 封禁天数；不填是永久
    remove_contents: bool = False  # 封禁时一并下架对方发过的全部帖子和留言（对付刷广告的）


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
        "avatar_key": target.avatar_key or "",
        "city_label": target.city_label or "",
        "bio": target.bio or "",
        "phone_verified": target.phone_verified,
        "status": target.status,
        "suspended_until": target.suspended_until,
        "suspend_reason": target.suspend_reason or "",
        "is_admin": target.is_admin,
        "is_super": target.is_super,
        "is_trusted": target.is_trusted,
        "two_factor": bool(target.totp_secret),
        "deleted": target.deleted_at is not None,
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


@guarded.post("/users/{user_id}/avatar/remove")
def remove_user_avatar(
    user_id: str,
    body: Reasoned,
    admin: User = Depends(require_admin),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    """头像不过审核，上传即公开；违规的由管理员在这里撤掉（图片文件一起删），对方回到首字色块。"""
    from app.api.v1.me import drop_avatar  # me 模块较重，只在这里用到

    target = session.get(User, user_id)
    if target is None or not target.avatar_key:
        raise APIError(409, "NO_CHANGE", "这个用户没有上传头像")
    drop_avatar(session, target)
    write_audit(session, admin.id, "admin.user.avatar_remove", "user", target.id, body.note)
    notify_user(session, target.id, f"你的头像已被管理员移除{_because(body.note)}")
    session.commit()
    return {"user_id": target.id, "avatar_key": ""}


RESET_LINK_HOURS = 24


@guarded.post("/users/{user_id}/reset-link")
def create_reset_link(
    user_id: str,
    admin: User = Depends(require_super),  # 拿到链接就能接管账号，所以只给超级管理员
    session: Session = Depends(get_db),
) -> dict[str, object]:
    """给忘记密码的用户生成一次性的重置凭证（24 小时内有效）。凭证只在这次响应里出现一次，库里只存哈希。"""
    target = session.get(User, user_id)
    if target is None or target.deleted_at is not None:
        raise APIError(404, "USER_NOT_FOUND", "用户不存在")
    # 之前没用掉的链接作废：同一时间只有最新的一个有效
    session.execute(delete(PasswordReset).where(PasswordReset.user_id == target.id, PasswordReset.used_at.is_(None)))
    token = new_refresh_token()
    expires_at = utcnow() + timedelta(hours=RESET_LINK_HOURS)
    session.add(PasswordReset(user_id=target.id, token_hash=hash_refresh_token(token), expires_at=expires_at))
    write_audit(session, admin.id, "admin.user.reset_link", "user", target.id)
    session.commit()
    return {"token": token, "expires_at": expires_at, "hours": RESET_LINK_HOURS}


class AdminFlagBody(Reasoned):
    is_admin: bool
    is_super: bool = False  # 只在 is_admin 为真时有意义


@guarded.post("/users/{user_id}/admin")
def set_user_admin(
    user_id: str,
    body: AdminFlagBody,
    admin: User = Depends(require_super),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    target = session.get(User, user_id)
    if target is None or target.deleted_at is not None:
        raise APIError(404, "USER_NOT_FOUND", "用户不存在")
    if target.id == admin.id:
        raise APIError(409, "CANNOT_CHANGE_SELF", "不能修改自己的管理员权限")  # 免得最后一个超级管理员把自己撤掉
    make_super = body.is_admin and body.is_super
    if target.is_admin == body.is_admin and target.is_super == make_super:
        raise APIError(409, "NO_CHANGE", "已经是这个状态")
    if body.is_admin and target.status != "active":
        raise APIError(409, "NO_CHANGE", "被封禁的账号不能设为管理员")
    target.is_admin = body.is_admin
    target.is_super = make_super
    if not body.is_admin:
        target.totp_secret = None
        # 对方手里的后台会话立刻作废（访问令牌本身每次请求都会查库，这里是让它续不了期）
        session.execute(delete(RefreshSession).where(RefreshSession.user_id == target.id, RefreshSession.admin.is_(True)))
    action = "admin.user.revoke" if not body.is_admin else "admin.user.grant_super" if make_super else "admin.user.grant"
    write_audit(session, admin.id, action, "user", target.id, body.note)
    session.commit()
    return {"user_id": target.id, "is_admin": target.is_admin, "is_super": target.is_super}


class TrustedBody(Reasoned):
    is_trusted: bool


@guarded.post("/users/{user_id}/trusted")
def set_user_trusted(
    user_id: str,
    body: TrustedBody,
    admin: User = Depends(require_super),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    """白名单：发帖 / 评论 / 视频不进人工审核（敏感词照拦），建房不受数量上限。"""
    target = session.get(User, user_id)
    if target is None or target.deleted_at is not None:
        raise APIError(404, "USER_NOT_FOUND", "用户不存在")
    if target.is_trusted == body.is_trusted:
        raise APIError(409, "NO_CHANGE", "已经是这个状态")
    target.is_trusted = body.is_trusted
    write_audit(session, admin.id, "admin.user.trust" if body.is_trusted else "admin.user.untrust", "user", target.id, body.note)
    session.commit()
    return {"user_id": target.id, "is_trusted": target.is_trusted}


def take_down_everything(session: Session, admin_id: str, user_id: str, note: str) -> tuple[int, int]:
    """下架这个人发过的全部帖子和留言，返回（帖子数，留言数）。每条都记审计，之后可以逐条恢复。"""
    now = utcnow()
    contents = session.scalars(select(Content).where(Content.author_id == user_id, Content.deleted_at.is_(None))).all()
    for content in contents:
        content.status = "deleted"
        content.deleted_at = now
        drop_pushes(session, content.id)
        write_audit(session, admin_id, "admin.content.remove", "content", content.id, note)
    comments = session.scalars(select(RoomComment).where(RoomComment.author_id == user_id, RoomComment.removed_at.is_(None))).all()
    for comment in comments:
        comment.status = "removed"
        comment.removed_at = now
        write_audit(session, admin_id, "admin.comment.remove", "comment", comment.id, note)
    return len(contents), len(comments)


@guarded.post("/users/{user_id}/status")
def set_user_status(
    user_id: str,
    body: UserStatusBody,
    admin: User = Depends(require_admin),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    target = session.get(User, user_id)
    if target is None or target.deleted_at is not None:
        raise APIError(404, "USER_NOT_FOUND", "用户不存在")
    # 不能封自己或其他管理员，免得后台被锁死；要处理管理员先撤销对方的权限。
    if body.status == "suspended" and (target.id == admin.id or target.is_admin):
        raise APIError(409, "CANNOT_SUSPEND_ADMIN", "不能封禁管理员")
    if target.status == body.status:
        raise APIError(409, "NO_CHANGE", "已经是这个状态")
    target.status = body.status
    removed = (0, 0)
    if body.status == "suspended":
        target.suspended_until = utcnow() + timedelta(days=body.days) if body.days else None
        target.suspend_reason = body.note
        session.execute(delete(RefreshSession).where(RefreshSession.user_id == target.id))  # 各设备上的登录立即失效
        if body.remove_contents:
            removed = take_down_everything(session, admin.id, target.id, f"随封禁「{target.display_name}」一并下架")
        detail = (f"{body.days} 天" if body.days else "永久") + (f"：{body.note}" if body.note else "")
        if body.remove_contents:
            detail += f"（一并下架 {removed[0]} 条帖子、{removed[1]} 条留言）"
        write_audit(session, admin.id, "admin.user.suspend", "user", target.id, detail[:300])
    else:
        target.suspended_until = None
        target.suspend_reason = None
        write_audit(session, admin.id, "admin.user.activate", "user", target.id, body.note)
        notify_user(session, target.id, "你的账号已恢复正常", actor_id=admin.id)
    session.commit()
    return {
        "user_id": target.id,
        "status": target.status,
        "suspended_until": target.suspended_until,
        "removed_posts": removed[0],
        "removed_comments": removed[1],
    }


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
        # 审核员要能看到视频本身：待审的帖子前台不公开，只能在这里看
        "video_url": f"/api/v1/uploads/{content.video_key}" if content.video_key else "",
        "embed_url": content.embed_source_url or "",  # 外链视频（如 YouTube）的原链接
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


def _release_uploads(session: Session, keys, content_id: str | None = None) -> list[str]:
    """彻底删除内容 / 留言时处理它们的图片视频：没有别的内容在用的，删掉上传登记并返回这些 key。

    文件本身要等数据库提交成功后再用 _delete_files 删（反过来的话，提交失败会留下图片打不开的帖子）。
    content_id 是正在删除的那条内容，判断"别处是否在用"时不算它。
    """
    orphaned: list[str] = []
    for key in set(keys) - {None, ""}:
        users = select(Content.id).where(
            (Content.image_key == key) | (Content.video_key == key) | Content.image_keys_json.contains(key)
        )
        if content_id is not None:  # 不能写成 id != None：SQL 里和 NULL 比较恒为假，会把在用的文件也当成没人用
            users = users.where(Content.id != content_id)
        if session.scalar(users.limit(1)) is None:
            orphaned.append(key)
            session.execute(delete(UploadObject).where(UploadObject.key == key))
    return orphaned


def _delete_files(keys: list[str]) -> int:
    """删掉这些上传文件，返回没删成的个数（存储暂时不可用时：记录已删，文件留着没人引用，稍后可清理）。"""
    left = 0
    for key in keys:
        try:
            delete_object(key)
        except APIError:
            left += 1
    return left


@guarded.post("/contents/{content_id}/delete")
def delete_content(
    content_id: str,
    body: Reasoned,
    admin: User = Depends(require_super),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    """彻底删除一条内容，连同它的留言、点赞收藏、举报记录和图片视频文件；不能恢复。只想让它不显示请用下架。"""
    content = session.get(Content, content_id)
    if content is None:
        raise APIError(404, "CONTENT_NOT_FOUND", "内容不存在")
    comments = session.scalars(select(RoomComment).where(RoomComment.content_id == content.id)).all()
    # 图片 / 视频文件一并删掉（不删的话知道原链接的人还能打开）；别的内容还在用的文件不动
    keys = set(image_keys_of(content)) | {content.video_key} | {comment.image_key for comment in comments}
    orphaned = _release_uploads(session, keys, content.id)
    # 附属记录显式删（SQLite 开发库没开外键级联）
    comment_ids = [comment.id for comment in comments]
    session.execute(delete(CommentLike).where(CommentLike.comment_id.in_(comment_ids)))
    session.execute(delete(RoomComment).where(RoomComment.id.in_(comment_ids)))
    for model in (ChannelItem, UserItemProgress, ModerationCase, Notification, ListingExt, ContactView, ContentReaction, RoomPostPush):
        session.execute(delete(model).where(model.content_id == content.id))
    # 内容删了以后日志里只剩 id，所以把标题写进备注
    detail = f"{content.title}（{content.type}）" + (f"：{body.note}" if body.note else "")
    write_audit(session, admin.id, "admin.content.delete", "content", content.id, detail[:300])
    notify_user(session, content.author_id, f"你的「{content.title}」已被管理员删除{_because(body.note)}", actor_id=admin.id)
    session.delete(content)
    session.commit()
    return {"deleted": True, "files_left": _delete_files(orphaned)}


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
        # 待审时被下架的帖子恢复后仍是待审，不能借「下架再恢复」绕过审核
        content.status = "published" if content.published_at is not None else "pending"
        content.deleted_at = None
    write_audit(session, admin.id, f"admin.content.{body.action}", "content", content.id, body.note)
    outcome = f"已被管理员下架{_because(body.note)}" if body.action == "remove" else "已恢复"
    notify_user(session, content.author_id, f"你的「{content.title}」{outcome}", content.id, admin.id)
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
        if comment.status == "removed" or comment.removed_at is not None:
            raise APIError(409, "NO_CHANGE", "这条留言已经删除")
        # 还在待审的留言删掉就等于审核拒绝：记成 rejected，之后「恢复」不能让它没审过就公开
        comment.status = "rejected" if comment.status == "pending" else "removed"
        comment.removed_at = utcnow()
    else:
        if comment.status != "removed" or not _was_taken_down(session, "comment", comment.id):
            raise APIError(409, "NO_CHANGE", "这条留言不是被管理员删除的，不能恢复")
        comment.status = "published"
        comment.removed_at = None
    write_audit(session, admin.id, f"admin.comment.{body.action}", "comment", comment.id, body.note)
    outcome = f"已被管理员删除{_because(body.note)}" if body.action == "remove" else "已恢复"
    notify_user(session, comment.author_id, f"你的留言「{comment.body[:30]}」{outcome}", comment.content_id, admin.id)
    session.commit()
    return {"comment_id": comment.id, "status": comment.status}


def _target_labels(session: Session, rows) -> dict[tuple[str, str], str]:
    """日志里「对象」的可读名字（用户名 / 帖子标题 / 频道名 / 留言开头），每种类型一次查完。原来只显示一串 id。"""
    wanted: dict[str, set[str]] = {}
    for row in rows:
        if row.target_type and row.target_id:
            wanted.setdefault(row.target_type, set()).add(row.target_id)
    lookups = {
        "user": (User.id, User.display_name),
        "content": (Content.id, Content.title),
        "channel": (Channel.id, Channel.name_hans),
        "comment": (RoomComment.id, RoomComment.body),
    }
    labels: dict[tuple[str, str], str] = {}
    for kind, ids in wanted.items():
        if kind not in lookups:
            continue
        key, text = lookups[kind]
        for target_id, label in session.execute(select(key, text).where(key.in_(ids))).all():
            labels[(kind, target_id)] = (label or "")[:40]
    return labels


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
    labels = _target_labels(session, page)
    return {
        "items": [
            {
                "id": row.id,
                "action": row.action,
                "actor_name": names.get(row.actor_id or "", ""),
                "target_type": row.target_type,
                "target_id": row.target_id,
                "target_label": labels.get((row.target_type or "", row.target_id or ""), ""),
                "detail": row.detail or "",
                "ip": row.ip or "",
                "user_agent": row.user_agent or "",
                "created_at": row.created_at,
            }
            for row in page
        ],
        "next_cursor": encode_cursor(page[-1].created_at.isoformat(), page[-1].id) if len(rows) > LIMIT else None,
    }


router.include_router(guarded)
