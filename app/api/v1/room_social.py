import re
from datetime import timedelta, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel, field_validator, model_validator
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.api.v1.auth import current_user, optional_user
from app.api.v1.uploads import owned_upload
from app.core.audit import write_audit
from app.core.db import get_db
from app.core.errors import APIError
from app.core.pagination import decode_cursor, encode_cursor, parse_added_at
from app.feed import author_names
from app.privacy import is_room_member
from app.recommend import country_blocked, is_roaming
from app.reports import ReportBody, report_receipt
from app.models import (
    Channel,
    ChannelItem,
    ChannelSubscription,
    ModerationCase,
    CommentLike,
    RoomComment,
    RoomJoinRequest,
    User,
    utcnow,
)

router = APIRouter(prefix="/channels")
_MENTION = re.compile(r"(?:^|(?<=\s))@([A-Za-z0-9_](?:[A-Za-z0-9._]{0,18}[A-Za-z0-9_])?)")
_MENTION_ANY = re.compile(r"(?:^|(?<=\s))@([\w\u4e00-\u9fff]{1,40})")
_KEYWORD = re.compile(r"#([\w\u4e00-\u9fff_]{1,12})")


def mention_count(body: str) -> int:
    return min(10, len(_MENTION_ANY.findall(body)))


def mention_handles(body: str) -> list[str]:
    found: list[str] = []
    for handle in _MENTION.findall(body):
        token = handle.lower()
        if token not in found:
            found.append(token)
        if len(found) == 10:
            break
    return found


def mention_users(session: Session, body: str) -> list[User]:
    users: list[User] = []
    for handle in mention_handles(body):
        person = session.scalar(
            select(User).where(User.handle == handle, User.deleted_at.is_(None), User.status == "active")
        )
        if person is not None:
            users.append(person)
    return users


def apply_comment_like(session: Session, user: User, comment: RoomComment) -> dict[str, object]:
    existing = session.get(CommentLike, (comment.id, user.id))
    if existing is None:
        session.add(CommentLike(comment_id=comment.id, user_id=user.id))
        liked = True
    else:
        session.delete(existing)
        liked = False
    session.commit()
    count = session.scalar(select(func.count()).select_from(CommentLike).where(CommentLike.comment_id == comment.id))
    return {"liked": liked, "like_count": int(count or 0)}


def comment_like_state(session: Session, user: User | None, comment_ids: list[str]) -> tuple[dict[str, int], set[str]]:
    if not comment_ids:
        return {}, set()
    counts = {
        comment_id: int(count)
        for comment_id, count in session.execute(
            select(CommentLike.comment_id, func.count())
            .where(CommentLike.comment_id.in_(comment_ids))
            .group_by(CommentLike.comment_id)
        ).all()
    }
    liked: set[str] = set()
    if user is not None:
        liked = set(
            session.scalars(
                select(CommentLike.comment_id).where(
                    CommentLike.comment_id.in_(comment_ids),
                    CommentLike.user_id == user.id,
                )
            ).all()
        )
    return counts, liked


class CommentBody(BaseModel):
    body: str
    content_id: str | None = None
    parent_id: str | None = None
    image_key: str | None = None

    @field_validator("body")
    @classmethod
    def body_length(cls, value: str) -> str:
        if len(value) > 1000:
            raise ValueError("留言需要 1 到 1000 个字")
        return value

    @model_validator(mode="after")
    def require_text_or_image(self) -> "CommentBody":
        if not self.body.strip() and not self.image_key:
            raise ValueError("留言需要文字或一张图片")
        return self


def _room(session: Session, channel_id: str) -> Channel:
    channel = session.get(Channel, channel_id)
    if channel is None or channel.kind != "room" or not channel.is_active:
        raise APIError(404, "CHANNEL_NOT_FOUND", "房间不存在")
    return channel


def _can_view(session: Session, room: Channel, user: User | None) -> bool:
    return not room.is_private or is_room_member(session, room, user)


def _aware(value):
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


@router.get("/{channel_id}/comments")
def list_comments(
    channel_id: str,
    cursor: str | None = None,
    limit: int = 20,
    user: User | None = Depends(optional_user),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    room = _room(session, channel_id)
    if not _can_view(session, room, user):
        raise APIError(403, "ROOM_PRIVATE", "这个房间需要先加入")
    bounded = min(max(limit, 1), 50)
    # 在数据库里按 (时间, id) 翻页，每页只读一页：原来每次把整个房间的留言读进内存再截取。
    query = (
        select(RoomComment)
        .where(
            RoomComment.room_id == room.id,
            RoomComment.removed_at.is_(None),
            (RoomComment.status == "published")
            | ((RoomComment.status == "pending") & (RoomComment.author_id == (user.id if user else ""))),
        )
        .order_by(RoomComment.created_at.desc(), RoomComment.id.desc())
    )
    parts = decode_cursor(cursor) if cursor else None
    after_at = parse_added_at(parts[1]) if parts and len(parts) == 2 else None
    if parts and after_at is not None:
        query = query.where(
            or_(
                RoomComment.created_at < after_at,
                and_(RoomComment.created_at == after_at, RoomComment.id < parts[0]),
            )
        )
    rows = session.scalars(query.limit(bounded + 1)).all()
    page = rows[:bounded]
    next_cursor = encode_cursor(page[-1].id, page[-1].created_at.isoformat()) if len(rows) > bounded else None
    counts, liked = comment_like_state(session, user, [row.id for row in page])
    authors = author_names(session, [row.author_id for row in page])
    items: list[dict[str, object]] = []
    for row in page:
        author_name, author_handle = authors.get(row.author_id, ("", ""))
        items.append(
            {
                "id": row.id,
                "author_id": row.author_id,
                "author_name": author_name,
                "author_handle": author_handle,
                "body": row.body,
                "image_key": row.image_key,
                "content_id": row.content_id,
                "parent_id": row.parent_id,
                "mention_count": row.mention_count,
                "mentions": [person.handle or "" for person in mention_users(session, row.body)],
                "keyword_count": row.keyword_count,
                "like_count": counts.get(row.id, 0),
                "liked": row.id in liked,
                "status": row.status,
                "created_at": row.created_at.isoformat(),
            }
        )
    payload: dict[str, object] = {"items": items}
    if next_cursor:
        payload["next_cursor"] = next_cursor
    return payload


@router.post("/{channel_id}/comments")
def create_comment(
    channel_id: str,
    body: CommentBody,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    room = _room(session, channel_id)
    if is_roaming(session, user):
        raise APIError(403, "ROAMING_READONLY", "跨国漫游下仅供浏览，发帖请切换至本地")
    if country_blocked(session, user, room):
        raise APIError(403, "REGION_BLOCKED", "当前国家看不到这个频道")
    if not _can_view(session, room, user):
        raise APIError(403, "ROOM_PRIVATE", "这个房间需要先加入")
    if body.content_id and body.parent_id:
        raise APIError(400, "VALIDATION_FAILED", "留言不能同时挂在帖子和另一条留言上")
    if body.content_id:
        item = session.get(ChannelItem, (room.id, body.content_id))
        if item is None:
            raise APIError(404, "CONTENT_NOT_FOUND", "这条内容不在房间里")
    if body.parent_id:
        parent = session.get(RoomComment, body.parent_id)
        if parent is None or parent.room_id != room.id or parent.removed_at is not None:
            raise APIError(404, "COMMENT_NOT_FOUND", "要回复的留言不存在")
    if body.image_key:
        owned_upload(session, user, body.image_key)
    now = utcnow()
    recent = session.scalars(
        select(RoomComment.created_at).where(RoomComment.room_id == room.id, RoomComment.author_id == user.id)
    ).all()
    if sum(1 for created_at in recent if _aware(created_at) >= now - timedelta(minutes=1)) >= 5:
        raise APIError(429, "RATE_LIMITED", "留言太频繁")
    if sum(1 for created_at in recent if _aware(created_at) >= now - timedelta(hours=1)) >= 20:
        raise APIError(429, "RATE_LIMITED", "这个小时的留言已达上限")
    comment = RoomComment(
        room_id=room.id,
        content_id=body.content_id,
        parent_id=body.parent_id,
        author_id=user.id,
        body=body.body,
        image_key=body.image_key,
        mention_count=mention_count(body.body),
        keyword_count=min(5, len(_KEYWORD.findall(body.body))),
    )
    session.add(comment)
    session.flush()
    write_audit(session, user.id, "comment.create", "comment", comment.id)
    session.commit()
    return {"comment_id": comment.id, "status": comment.status}


@router.post("/{channel_id}/comments/{comment_id}/like")
def toggle_comment_like(
    channel_id: str,
    comment_id: str,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    room = _room(session, channel_id)
    if not _can_view(session, room, user):
        raise APIError(403, "ROOM_PRIVATE", "这个房间需要先加入")
    comment = session.get(RoomComment, comment_id)
    if comment is None or comment.room_id != room.id or comment.removed_at is not None or comment.status != "published":
        raise APIError(404, "COMMENT_NOT_FOUND", "留言不存在")
    return apply_comment_like(session, user, comment)


@router.post("/{channel_id}/comments/{comment_id}/report")
def report_comment(
    channel_id: str,
    comment_id: str,
    body: ReportBody,
    user: User | None = Depends(optional_user),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    room = _room(session, channel_id)
    comment = session.get(RoomComment, comment_id)
    if comment is None or comment.room_id != room.id or comment.removed_at is not None or comment.status != "published":
        raise APIError(404, "COMMENT_NOT_FOUND", "留言不存在")
    if user is not None and comment.author_id == user.id:
        raise APIError(403, "SELF_REPORT", "不能举报自己的留言")
    if user is not None:
        existing = session.scalar(
            select(ModerationCase.id).where(
                ModerationCase.reported_comment_id == comment.id,
                ModerationCase.reporter_id == user.id,
            )
        )
        if existing:
            raise APIError(409, "DUPLICATE_REPORT", "你已经举报过这条留言")
    else:
        # 游客没法按人去重：同一条留言已有待处理的游客举报就直接复用。
        pending = session.scalar(
            select(ModerationCase).where(
                ModerationCase.reported_comment_id == comment.id,
                ModerationCase.reporter_id.is_(None),
                ModerationCase.status == "open",
            )
        )
        if pending is not None:
            return report_receipt(pending)
    case = ModerationCase(
        reported_comment_id=comment.id,
        reporter_id=user.id if user else None,
        reason=body.reason,
        detail=body.detail,
    )
    session.add(case)
    session.flush()
    write_audit(session, user.id if user else None, "comment.report", "comment", comment.id)
    session.commit()
    return report_receipt(case)


@router.delete("/{channel_id}/comments/{comment_id}")
def remove_comment(
    channel_id: str,
    comment_id: str,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    room = _room(session, channel_id)
    comment = session.get(RoomComment, comment_id)
    if comment is None or comment.room_id != room.id:
        raise APIError(404, "COMMENT_NOT_FOUND", "留言不存在")
    if comment.author_id != user.id and room.owner_id != user.id:
        raise APIError(403, "FORBIDDEN", "不能处理这条留言")
    comment.status = "removed"
    comment.removed_at = utcnow()
    write_audit(session, user.id, "comment.remove", "comment", comment.id)
    session.commit()
    return {"comment_id": comment.id, "status": comment.status}


@router.post("/{channel_id}/join-requests")
def request_join(
    channel_id: str,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    room = _room(session, channel_id)
    if country_blocked(session, user, room):
        raise APIError(403, "REGION_BLOCKED", "当前国家看不到这个频道")
    if not room.is_private:
        raise APIError(409, "ROOM_PUBLIC", "公开房间直接加入即可")
    if room.owner_id == user.id or session.get(ChannelSubscription, (user.id, room.id)) is not None:
        raise APIError(409, "ALREADY_MEMBER", "你已经在这个房间里")
    existing = session.scalar(
        select(RoomJoinRequest).where(RoomJoinRequest.room_id == room.id, RoomJoinRequest.user_id == user.id)
    )
    if existing is None:
        existing = RoomJoinRequest(room_id=room.id, user_id=user.id)
        session.add(existing)
        session.commit()
    return {"request_id": existing.id, "status": "pending"}


@router.get("/{channel_id}/join-requests")
def list_join_requests(
    channel_id: str,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, list[dict[str, str]]]:
    room = _room(session, channel_id)
    if room.owner_id != user.id:
        raise APIError(403, "FORBIDDEN", "只有房主可以查看申请")
    rows = session.scalars(select(RoomJoinRequest).where(RoomJoinRequest.room_id == room.id)).all()
    people = {person.id: person for person in session.scalars(select(User).where(User.id.in_([row.user_id for row in rows] or [""]))).all()}
    return {"items": [
        {
            "request_id": row.id,
            "user_id": row.user_id,
            "display_name": people[row.user_id].display_name if row.user_id in people else "用户",
            "handle": people[row.user_id].handle if row.user_id in people else "",
        }
        for row in rows
    ]}


@router.post("/{channel_id}/join-requests/{request_id}/approve")
def approve_join(
    channel_id: str,
    request_id: str,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, bool]:
    room = _room(session, channel_id)
    if room.owner_id != user.id:
        raise APIError(403, "FORBIDDEN", "只有房主可以通过申请")
    request = session.get(RoomJoinRequest, request_id)
    if request is None or request.room_id != room.id:
        raise APIError(404, "REQUEST_NOT_FOUND", "没有这条申请")
    if session.get(ChannelSubscription, (request.user_id, room.id)) is None:
        session.add(ChannelSubscription(user_id=request.user_id, channel_id=room.id))
        room.subscriber_count += 1
    session.delete(request)
    write_audit(session, user.id, "room.join.approve", "channel", room.id)
    session.commit()
    return {"joined": True}


@router.post("/{channel_id}/join-requests/{request_id}/reject")
def reject_join(
    channel_id: str,
    request_id: str,
    user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, bool]:
    room = _room(session, channel_id)
    if room.owner_id != user.id:
        raise APIError(403, "FORBIDDEN", "只有房主可以拒绝申请")
    request = session.get(RoomJoinRequest, request_id)
    if request is None or request.room_id != room.id:
        raise APIError(404, "REQUEST_NOT_FOUND", "没有这条申请")
    session.delete(request)
    write_audit(session, user.id, "room.join.reject", "channel", room.id)
    session.commit()
    return {"rejected": True}
