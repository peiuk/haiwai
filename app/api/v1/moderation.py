from fastapi import APIRouter, Depends
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.auth import current_user
from app.api.v1.room_social import mention_users
from app.core.audit import write_audit
from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import APIError
from app.models import Channel, ChannelItem, Content, ModerationCase, Notification, RoomComment, User, UserFollow, utcnow
from app.rooms import drop_pushes, notify_room_update

router = APIRouter(prefix="/moderation")


def _require_moderator(user: User) -> None:
    # 只有管理员能审（python -m app.make_admin 设置）；单元测试里任何登录用户都能审，免得每个用例都先提权。
    settings = get_settings()
    if user.is_admin or (settings.testing and settings.app_env == "dev"):
        return
    raise APIError(403, "FORBIDDEN", "需要管理员权限")


class DecisionBody(BaseModel):
    decision: str

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
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    _require_moderator(user)
    content = session.get(Content, content_id)
    if content is None or content.deleted_at is not None:
        raise APIError(404, "CONTENT_NOT_FOUND", "内容不存在")
    if content.status != "pending":
        raise APIError(409, "CONTENT_ALREADY_DECIDED", "这条内容已经审过")
    now = utcnow()
    if body.decision == "approve":
        content.status = "published"
        content.published_at = now
        items = session.scalars(select(ChannelItem).where(ChannelItem.content_id == content.id)).all()
        for item in items:
            item.added_at = now
            channel = session.get(Channel, item.channel_id)
            if channel is not None and channel.kind == "room" and not channel.is_active and channel.review_status == "pending":
                channel.is_active = True
                channel.review_status = "approved"
            if channel is not None:
                notify_room_update(session, channel, content)
    else:
        content.status = "rejected"
        drop_pushes(session, content.id)
    write_audit(session, user.id, f"moderation.{body.decision}", "content", content.id)
    session.commit()
    return {"content_id": content.id, "status": content.status}


@router.post("/comments/{comment_id}/decision")
def decide_comment(
    comment_id: str,
    body: DecisionBody,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    _require_moderator(user)
    comment = session.get(RoomComment, comment_id)
    if comment is None or comment.removed_at is not None:
        raise APIError(404, "COMMENT_NOT_FOUND", "留言不存在")
    if comment.status != "pending":
        raise APIError(409, "CONTENT_ALREADY_DECIDED", "这条留言已经审过")
    if body.decision == "approve":
        comment.status = "published"
        author = session.get(User, comment.author_id)
        name = author.display_name if author else "有人"
        for person in mention_users(session, comment.body):
            if person.id == comment.author_id:
                continue
            if session.get(UserFollow, (person.id, comment.author_id)) is None:
                continue
            session.add(
                Notification(
                    user_id=person.id,
                    kind="mention",
                    body=f"{name} 在留言里提到了你"[:200],
                    content_id=comment.content_id,
                )
            )
    else:
        comment.status = "rejected"
        comment.removed_at = utcnow()
    write_audit(session, user.id, f"moderation.{body.decision}", "comment", comment.id)
    session.commit()
    return {"comment_id": comment.id, "status": comment.status}


class CaseDecisionBody(BaseModel):
    decision: str

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
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    _require_moderator(user)
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
            write_audit(session, user.id, "moderation.remove", "comment", comment.id)
        else:
            outcome = "未删除"
            write_audit(session, user.id, "moderation.dismiss", "comment", comment.id)
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
            write_audit(session, user.id, "moderation.remove", "channel", channel.id)
        else:
            outcome = "未下架"
            write_audit(session, user.id, "moderation.dismiss", "channel", channel.id)
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
            reported.status = "suspended"
            outcome = "已限制"
            write_audit(session, user.id, "moderation.remove", "user", reported.id)
        else:
            outcome = "未限制"
            write_audit(session, user.id, "moderation.dismiss", "user", reported.id)
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
        write_audit(session, user.id, "moderation.remove", "content", content.id)
    else:
        outcome = "未下架"
        write_audit(session, user.id, "moderation.dismiss", "content", content.id)
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
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    _require_moderator(user)
    channel = session.get(Channel, channel_id)
    if channel is None or channel.owner_id is None:
        raise APIError(404, "CHANNEL_NOT_FOUND", "频道不存在")
    if channel.review_status != "pending":
        raise APIError(409, "CHANNEL_ALREADY_DECIDED", "这个频道已经审过")
    if body.decision == "approve":
        channel.review_status = "approved"
        channel.is_active = True
        write_audit(session, user.id, "channel.approve", "channel", channel.id)
    else:
        channel.review_status = "rejected"
        channel.is_active = False
        write_audit(session, user.id, "channel.reject", "channel", channel.id)
    session.commit()
    return {"channel_id": channel.id, "review_status": channel.review_status}
