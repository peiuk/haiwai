from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.admin import _because, notify_user, require_admin
from app.api.v1.room_social import publish_comment
from app.core.audit import write_audit
from app.core.db import get_db
from app.core.errors import APIError
from app.models import Channel, ChannelItem, Content, ModerationCase, Notification, RoomComment, User, UserFollow, utcnow
from app.rooms import drop_pushes, notify_room_update

router = APIRouter(prefix="/moderation")


def require_moderator(admin: User = Depends(require_admin)) -> User:
    """审核权限就是管理员权限。单独成一个依赖，只是为了让测试能替换它（见 tests/conftest.py）。"""
    return admin


class DecisionBody(BaseModel):
    decision: str
    note: str = Field(default="", max_length=300)  # 处理理由，记入审计日志

    @field_validator("decision")
    @classmethod
    def known_decision(cls, value: str) -> str:
        if value not in {"approve", "reject"}:
            raise ValueError("决定只能是通过或拒绝")
        return value


@router.post("/{content_id}/decision")
def decide(
    content_id: str,
    body: DecisionBody,
    user: User = Depends(require_moderator),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    content = session.get(Content, content_id)
    if content is None or content.deleted_at is not None:
        raise APIError(404, "CONTENT_NOT_FOUND", "内容不存在")
    if content.status != "pending":
        raise APIError(409, "CONTENT_ALREADY_DECIDED", "这条内容已经审过")
    now = utcnow()
    if body.decision == "approve":
        content.status = "published"
        # 公开过、被举报后先隐藏的帖子复核通过：原样放回去。只有第一次公开才算新帖（改时间、通知房间成员），
        # 不然一条旧帖被举报一轮就顶到信息流最前面，还给所有人再推一遍。
        first_time = content.published_at is None
        if first_time:
            content.published_at = now
        items = session.scalars(select(ChannelItem).where(ChannelItem.content_id == content.id)).all()
        for item in items:
            channel = session.get(Channel, item.channel_id)
            if channel is not None and channel.kind == "room" and not channel.is_active and channel.review_status == "pending":
                channel.is_active = True
                channel.review_status = "approved"
            if first_time:
                item.added_at = now
                if channel is not None:
                    notify_room_update(session, channel, content)
    else:
        content.status = "rejected"
        drop_pushes(session, content.id)
    note = body.note.strip() or None
    outcome = "已通过审核" if body.decision == "approve" else f"没有通过审核{_because(note)}"
    notify_user(session, content.author_id, f"你的「{content.title}」{outcome}", content.id, user.id)
    write_audit(session, user.id, f"moderation.{body.decision}", "content", content.id, body.note.strip() or None)
    session.commit()
    return {"content_id": content.id, "status": content.status}


@router.post("/comments/{comment_id}/decision")
def decide_comment(
    comment_id: str,
    body: DecisionBody,
    user: User = Depends(require_moderator),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    comment = session.get(RoomComment, comment_id)
    if comment is None or comment.removed_at is not None:
        raise APIError(404, "COMMENT_NOT_FOUND", "留言不存在")
    if comment.status != "pending":
        raise APIError(409, "CONTENT_ALREADY_DECIDED", "这条留言已经审过")
    if body.decision == "approve":
        publish_comment(session, comment)
    else:
        comment.status = "rejected"
        comment.removed_at = utcnow()
        notify_user(
            session,
            comment.author_id,
            f"你的留言「{comment.body[:30]}」没有通过审核{_because(body.note.strip() or None)}",
            comment.content_id,
            user.id,
        )
    write_audit(session, user.id, f"moderation.{body.decision}", "comment", comment.id, body.note.strip() or None)
    session.commit()
    return {"comment_id": comment.id, "status": comment.status}


class CaseDecisionBody(BaseModel):
    decision: str
    note: str = Field(default="", max_length=300)  # 处理理由，记入审计日志

    @field_validator("decision")
    @classmethod
    def known_case_decision(cls, value: str) -> str:
        if value not in {"remove", "dismiss"}:
            raise ValueError("决定只能是下架或驳回")
        return value


@router.post("/cases/{case_id}/decision")
def decide_case(
    case_id: str,
    body: CaseDecisionBody,
    user: User = Depends(require_moderator),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    case = session.get(ModerationCase, case_id)
    if case is None or case.status != "open":
        raise APIError(404, "CASE_NOT_FOUND", "举报不存在")
    now = utcnow()
    case.status = "closed"
    case.decision = body.decision
    case.decided_at = now
    if case.reported_comment_id:
        comment = session.get(RoomComment, case.reported_comment_id)
        if comment is None:
            raise APIError(404, "COMMENT_NOT_FOUND", "留言不存在")
        if body.decision == "remove":
            comment.removed_at = now
            comment.status = "removed"
            outcome = "已删除"
            notify_user(
                session,
                comment.author_id,
                f"你的留言「{comment.body[:30]}」被举报后已删除{_because(body.note.strip() or None)}",
                comment.content_id,
                user.id,
            )
            write_audit(session, user.id, "moderation.remove", "comment", comment.id, body.note.strip() or None)
        else:
            outcome = "未删除"
            write_audit(session, user.id, "moderation.dismiss", "comment", comment.id, body.note.strip() or None)
        if case.reporter_id is not None:
            session.add(
                Notification(
                    user_id=case.reporter_id,
                    kind="moderation.decision",
                    body=f"你举报的留言{outcome}",
                )
            )
        session.commit()
        return {"comment_id": comment.id, "status": comment.status}
    if case.reported_channel_id and case.content_id is None and case.reported_user_id is None:
        channel = session.get(Channel, case.reported_channel_id)
        if channel is None:
            raise APIError(404, "CHANNEL_NOT_FOUND", "频道不存在")
        if body.decision == "remove":
            channel.is_active = False
            outcome = "已下架"
            write_audit(session, user.id, "moderation.remove", "channel", channel.id, body.note.strip() or None)
        else:
            outcome = "未下架"
            write_audit(session, user.id, "moderation.dismiss", "channel", channel.id, body.note.strip() or None)
        if case.reporter_id is not None:
            session.add(
                Notification(
                    user_id=case.reporter_id,
                    kind="moderation.decision",
                    body=f"你举报的房间「{channel.name_hans}」{outcome}",
                )
            )
        session.commit()
        return {"channel_id": channel.id, "status": "removed" if body.decision == "remove" else "kept"}
    if case.reported_user_id and case.content_id is None:
        reported = session.get(User, case.reported_user_id)
        if reported is None:
            raise APIError(404, "USER_NOT_FOUND", "用户不存在")
        if body.decision == "remove":
            # 和后台「封禁用户」同一条规则：不能封管理员（包括自己），免得后台被锁死
            if reported.is_admin:
                raise APIError(409, "CANNOT_SUSPEND_ADMIN", "不能封禁管理员；要处理请先撤销对方的管理员权限")
            reported.status = "suspended"
            reported.suspend_reason = body.note.strip() or None
            outcome = "已限制"
            write_audit(session, user.id, "moderation.remove", "user", reported.id, body.note.strip() or None)
        else:
            outcome = "未限制"
            write_audit(session, user.id, "moderation.dismiss", "user", reported.id, body.note.strip() or None)
        if case.reporter_id is not None:
            session.add(
                Notification(
                    user_id=case.reporter_id,
                    kind="moderation.decision",
                    body=f"你举报的用户「{reported.display_name}」{outcome}",
                )
            )
        session.commit()
        return {"reported_user_id": reported.id, "status": reported.status}
    content = session.get(Content, case.content_id)
    if content is None:
        raise APIError(404, "CONTENT_NOT_FOUND", "内容不存在")
    if body.decision == "remove":
        content.status = "deleted"
        content.deleted_at = now
        drop_pushes(session, content.id)
        outcome = "已下架"
        notify_user(
            session,
            content.author_id,
            f"你的「{content.title}」被举报后已下架{_because(body.note.strip() or None)}",
            content.id,
            user.id,
        )
        write_audit(session, user.id, "moderation.remove", "content", content.id, body.note.strip() or None)
    else:
        outcome = "未下架"
        write_audit(session, user.id, "moderation.dismiss", "content", content.id, body.note.strip() or None)
    if case.reporter_id is not None:
        session.add(
            Notification(
                user_id=case.reporter_id,
                kind="moderation.decision",
                body=f"你举报的「{content.title}」{outcome}",
                content_id=content.id,
            )
        )
    session.commit()
    return {"content_id": content.id, "status": content.status}


@router.post("/channels/{channel_id}/decision")
def decide_channel(
    channel_id: str,
    body: DecisionBody,
    user: User = Depends(require_moderator),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    channel = session.get(Channel, channel_id)
    if channel is None or channel.owner_id is None:
        raise APIError(404, "CHANNEL_NOT_FOUND", "频道不存在")
    if channel.review_status != "pending":
        raise APIError(409, "CHANNEL_ALREADY_DECIDED", "这个频道已经审过")
    if body.decision == "approve":
        channel.review_status = "approved"
        channel.is_active = True
        write_audit(session, user.id, "channel.approve", "channel", channel.id, body.note.strip() or None)
    else:
        channel.review_status = "rejected"
        channel.is_active = False
        write_audit(session, user.id, "channel.reject", "channel", channel.id, body.note.strip() or None)
    session.commit()
    return {"channel_id": channel.id, "review_status": channel.review_status}
